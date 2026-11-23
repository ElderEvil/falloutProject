import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cli.simulate_resources import ResourceEconomyConfig, _build_scenario, simulate
from app.core.enums import AgeGroupEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent
from app.core.game_config import game_config
from app.crud.resource import VaultResourceData
from app.models import Dweller, Storage
from app.models.room import Room
from app.models.vault import Vault
from app.options.races import DISCOMFORT_EFFECTS, DISCOMFORT_PRODUCTION_FLOOR, DiscomfortSeverity
from app.schemas.vault import ResourceLevelWarning, ResourceProduction, ResourceTickEvents
from app.services.resource_manager_service import ResourceManager
from app.services.vault.scenario_service import SHORT_RATIONS_SCENARIO, vault_scenario_service
from app.utils.item_factory import build_outfit
from app.utils.resource_warnings import get_resource_warnings

RM = "app.services.resource_manager_service"
STARTER_ROOM_OUTPUT = 28  # catalog output (2*S*(L+4))-2 at tier 1, size 3


def _room(name: str, ability: SPECIALEnum, output: float, **fields) -> Room:
    fields.setdefault("tier", 1)
    fields.setdefault("size", 1)
    return Room(name=name, category=RoomTypeEnum.PRODUCTION, ability=ability, output=output, **fields)


def _vault(**fields) -> Vault:
    base = {"power": 75, "food": 50, "water": 50, "power_max": 150, "food_max": 150, "water_max": 150}
    return Vault(**(base | fields))


def test_short_rations_produces_less_food_and_water_with_the_same_workers():
    standard = _vault()
    challenge = standard.model_copy(update={"scenario_key": SHORT_RATIONS_SCENARIO})
    rooms = [
        _room(name, ability, 10, size=3)
        for name, ability in (
            ("Power Generator", SPECIALEnum.STRENGTH),
            ("Diner", SPECIALEnum.AGILITY),
            ("Water Treatment", SPECIALEnum.PERCEPTION),
        )
    ]
    crews = [(room, [Dweller(strength=5, agility=5, perception=5)]) for room in rooms]
    manager = ResourceManager()
    # Ten minutes: objective counters are integer-valued, and at the retuned rates a single
    # minute of one-worker production rounds to zero.
    ordinary_update, ordinary = manager.calculate_resource_window(standard, rooms, 1, crews, 600)
    challenge_update, reduced = manager.calculate_resource_window(challenge, rooms, 1, crews, 600)

    assert reduced.consumption == ordinary.consumption
    assert reduced.production.power == ordinary.production.power
    scenario = vault_scenario_service.get(SHORT_RATIONS_SCENARIO)
    assert scenario is not None
    expected = scenario.food_water_multiplier
    assert reduced.production.food == pytest.approx(ordinary.production.food * expected)
    assert reduced.production.water == pytest.approx(ordinary.production.water * expected)
    assert reduced.objective_production.food < ordinary.objective_production.food
    assert challenge_update.food < ordinary_update.food


def test_short_rations_makes_feeding_the_vault_a_staffing_decision():
    """The experiment must cost something from the first minute.

    Mirrors docs/backend/BALANCE_PLAYTEST.md: the seeded starter (nine dwellers,
    two SPECIAL-5 cooks) and ordinary growth (SPECIAL-3 cooks).
    """
    diner = _room("Diner", SPECIALEnum.AGILITY, 28, size=3)
    manager = ResourceManager()

    def net_food(population: int, cooks: int, special: int) -> float:
        vault = _vault(power=100, food=100, water=100, scenario_key=SHORT_RATIONS_SCENARIO)
        crew = [(diner, [Dweller(agility=special) for _ in range(cooks)])]
        # Ten minutes: the vault update is integer-valued, so a one-minute window
        # rounds a tight net (+0.35/min) away to zero.
        update, _ = manager.calculate_resource_window(vault, [diner], float(population), crew, 600)
        return (update.food - vault.food) / 10

    starter = net_food(9, 2, 5)
    scenario = vault_scenario_service.get(SHORT_RATIONS_SCENARIO)
    assert scenario is not None
    reducer = scenario.food_water_multiplier
    assert -0.5 < starter < 0.5, f"the experiment is near break-even at the seeded crew, got {starter:+.2f}/min"
    assert net_food(9, 3, 5) > 0, "one more cook must clear the shortfall"

    # Recovery is a computed boundary rather than a magic cook count: short rations must always cost
    # extra cooks, and the count follows the shipped rates instead of being pinned to one wave.
    per_cook = 28 * 3 * game_config.resource.base_production_rate * 60 * reducer
    draw = 20 * game_config.resource.food_consumption_per_dweller * 60
    cooks_needed = math.ceil(draw / per_cook)
    assert net_food(20, cooks_needed - 1, 3) < 0
    # At the exact boundary the margin is a rounding error against an integer-valued vault, so the
    # boundary asserts break-even and a small staffing margin proves the recovery.
    assert net_food(20, cooks_needed, 3) >= 0
    assert net_food(20, cooks_needed + 2, 3) > 0


def test_check_resource_warnings():
    vault = Vault(power_max=100, food_max=100, water_max=100)

    assert len(get_resource_warnings(vault, {"power": 50.0, "food": 50.0, "water": 50.0})) == 0

    warnings = get_resource_warnings(vault, {"power": 19.0, "food": 50.0, "water": 50.0})
    assert len(warnings) == 1
    assert isinstance(warnings[0], ResourceLevelWarning)
    assert warnings[0].type == "low_power"

    warnings = get_resource_warnings(vault, {"power": 4.0, "food": 50.0, "water": 50.0})
    assert len(warnings) == 1
    assert warnings[0].type == "critical_power"

    warnings = get_resource_warnings(vault, {"power": 4.0, "food": 19.0, "water": 50.0})
    assert len(warnings) == 2
    types = [warning.type for warning in warnings]
    assert "critical_power" in types
    assert "low_food" in types

    # Zero water means dehydration, not a plain critical-water warning.
    types = [warning.type for warning in get_resource_warnings(vault, {"power": 50.0, "food": 50.0, "water": 0.0})]
    assert "critical_water" not in types
    assert "critical_dehydration" in types


def test_power_outage_production():
    manager = ResourceManager()
    crews = [
        (_room("Power", SPECIALEnum.STRENGTH, 10.0), [Dweller(strength=10)]),
        (_room("Diner", SPECIALEnum.AGILITY, 10.0), [Dweller(agility=10)]),
    ]

    normal = manager._calculate_production(crews, seconds_passed=60, current_power=10)
    assert normal["power"] > 0
    assert normal["food"] > 0

    outage = manager._calculate_production(crews, seconds_passed=60, current_power=0)
    assert outage["power"] > 0  # Power plants still work
    assert outage["food"] == 0  # Diners stop working


@pytest.mark.parametrize(
    ("starting_stimpacks", "capacity", "output", "expected_delta"), [(4, 5, 33, 1), (5, 5, 100, 0)]
)
@pytest.mark.asyncio
async def test_medical_events_match_persisted_storage_change(
    vault: Vault, starting_stimpacks: int, capacity: int, output: int, expected_delta: int
):
    """Medical collection events must match rounded, capacity-limited storage changes."""
    vault.power = 10
    storage = Storage(vault_id=vault.id, stimpack=starting_stimpacks)
    medbay = _room("Medbay", SPECIALEnum.INTELLIGENCE, output, capacity=capacity)
    resource_data = VaultResourceData(
        vault=vault,
        storage=storage,
        rooms=[medbay],
        dweller_count=0,
        rooms_with_dwellers=[(medbay, [Dweller(intelligence=1)])],
    )

    with (
        patch(f"{RM}.resource_crud.get_vault_resource_data", new_callable=AsyncMock, return_value=resource_data),
        patch(f"{RM}.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(f"{RM}.relationship_crud.get_involving_any", new_callable=AsyncMock, return_value=[]),
    ):
        _, events = await ResourceManager().process_vault_resources(MagicMock(), vault.id, 60)
        await ResourceManager.emit_production_events(vault.id, events)

    resources = emit.await_args.args[2]["resources"] if emit.await_args else {}
    assert storage.stimpack == starting_stimpacks + expected_delta
    assert resources.get("stimpack", 0) == expected_delta


def test_a_window_that_runs_dry_partway_reports_only_its_dry_seconds() -> None:
    """Deprivation charges dry time, so the resource window has to measure it: 7 food at 2.8/min lasts two steps."""
    manager = ResourceManager()
    vault = Vault(power=100, power_max=100, food=7, food_max=100, water=100, water_max=100)

    _, events = manager.calculate_resource_window(
        vault, [], dweller_count=20, rooms_with_dwellers=[], seconds_passed=600
    )

    assert events.dry_seconds == {"food": 8 * 60, "water": 0}


@pytest.mark.asyncio
async def test_production_events_emit_one_batched_event(vault: Vault):
    events = ResourceTickEvents(
        production=ResourceProduction(power=12.4, food=0.0, water=3.6, stimpack=1.0, radaway=0.0)
    )

    with patch(f"{RM}.event_bus.emit", new_callable=AsyncMock) as emit:
        await ResourceManager.emit_production_events(vault.id, events)

    emit.assert_awaited_once()
    event_type, vault_id, payload = emit.await_args.args
    assert event_type == GameEvent.RESOURCE_COLLECTED
    assert vault_id == vault.id
    assert payload == {"resources": {"power": 12, "water": 3, "stimpack": 1}, "source": "production"}


@pytest.mark.asyncio
async def test_production_events_skip_an_empty_batch(vault: Vault):
    """A tick with no positive production must not emit an empty event."""
    with patch(f"{RM}.event_bus.emit", new_callable=AsyncMock) as emit:
        await ResourceManager.emit_production_events(vault.id, ResourceTickEvents())

    emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_junior_worker_assists_production_at_the_reduced_rate():
    manager = ResourceManager()
    room = _room("Power", SPECIALEnum.STRENGTH, 10.0)
    adult = Dweller(strength=10)
    junior = Dweller(strength=10, age_group=AgeGroupEnum.TEEN, apprentice_stat=SPECIALEnum.STRENGTH)

    adult_only = manager._calculate_production([(room, [adult])], seconds_passed=60, current_power=10)["power"]
    with_junior = manager._calculate_production([(room, [adult, junior])], seconds_passed=60, current_power=10)["power"]

    assert adult_only > 0
    assert with_junior == pytest.approx(adult_only * (1 + game_config.resource.junior_worker_output_multiplier))


def test_base_production_rate_default_matches_resource_economy_baseline() -> None:
    """The shipped default reproduces the documented per-tick starts across staffing states."""
    assert game_config.resource.base_production_rate == pytest.approx(0.00020)


@pytest.mark.parametrize(
    ("workers_per_room", "expected_net_per_tick"),
    [
        (2, {"power": 5, "food": 2, "water": 2}),
        (1, {"power": 2, "food": 0, "water": 0}),
        (0, {"power": -2, "food": -1, "water": -1}),
    ],
)
def test_starter_vault_meets_resource_economy_baseline_contract(
    workers_per_room: int, expected_net_per_tick: dict[str, int]
) -> None:
    result = simulate(
        ResourceEconomyConfig(
            population=9, workers_per_room=workers_per_room, worker_special=5, room_tier=1, room_size=3
        )
    )
    persisted_per_tick = {
        resource: round(result.initial_rates_per_minute[resource]) for resource in expected_net_per_tick
    }
    assert persisted_per_tick == expected_net_per_tick


@pytest.mark.asyncio
async def test_live_tick_matches_offline_kernel_production_at_default_rate(vault: Vault) -> None:
    """The live DB tick and the offline kernel must apply the same configured production rate."""
    vault.power = 100
    manager = ResourceManager()
    rooms = [
        _room("Power Generator", SPECIALEnum.STRENGTH, float(STARTER_ROOM_OUTPUT), size=3),
        _room("Diner", SPECIALEnum.AGILITY, float(STARTER_ROOM_OUTPUT), size=3),
        _room("Water Treatment", SPECIALEnum.PERCEPTION, float(STARTER_ROOM_OUTPUT), size=3),
    ]
    rooms_with_dwellers = [
        (rooms[0], [Dweller(strength=5), Dweller(strength=5)]),
        (rooms[1], [Dweller(agility=5), Dweller(agility=5)]),
        (rooms[2], [Dweller(perception=5), Dweller(perception=5)]),
    ]
    offline = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=vault.power)
    resource_data = VaultResourceData(
        vault=vault, storage=None, rooms=rooms, dweller_count=9, rooms_with_dwellers=rooms_with_dwellers
    )

    with (
        patch(f"{RM}.resource_crud.get_vault_resource_data", new_callable=AsyncMock, return_value=resource_data),
        patch(f"{RM}.event_bus.emit", new_callable=AsyncMock),
        patch(f"{RM}.relationship_crud.get_involving_any", new_callable=AsyncMock, return_value=[]),
    ):
        _, events = await manager.process_vault_resources(MagicMock(), vault.id, 60)

    for resource in ("power", "food", "water"):
        assert getattr(events.production, resource) == pytest.approx(offline[resource])


def test_offline_window_matches_per_tick_fractional_carry() -> None:
    cfg = ResourceEconomyConfig(
        population=9,
        workers_per_room=2,
        worker_special=5,
        room_tier=1,
        room_size=3,
        starting_power=50,
        starting_food=50,
        starting_water=50,
        # The shipped rate saturates a 100-cap starter on both paths, hiding the
        # divergence; a high cap isolates the rounding kernel itself.
        resource_max=1_000_000,
    )
    vault, rooms, rooms_with_dwellers = _build_scenario(cfg)
    update, _ = ResourceManager().calculate_resource_window(vault, rooms, cfg.population, rooms_with_dwellers, 3600)
    per_tick = simulate(cfg).final_resources
    assert {key: getattr(update, key) for key in ("power", "food", "water")} == per_tick


def _seeded_net(prepared, dweller_count: int, crews: list[list[Dweller]], resource: str, room_prefix: str) -> float:
    """Net live per-minute change for one resource over the real seeded room set."""
    manager = ResourceManager()
    rooms = [
        *prepared.infrastructure,
        *prepared.capacity,
        *prepared.production,
        *prepared.misc,
        *prepared.training,
        *prepared.arena,
        *prepared.crafting,
    ]
    matched = [room for room in prepared.production if str(room.name).lower().startswith(room_prefix)]
    consumption = manager._calculate_consumption(rooms, dweller_count, seconds_passed=60)[resource]
    produced = manager._calculate_production(
        list(zip(matched, crews, strict=True)), seconds_passed=60, current_power=50
    )[resource]
    return produced - consumption


def _adults(strength: int, count: int) -> list[Dweller]:
    return [Dweller(strength=strength) for _ in range(count)]


def _apprentice(value: int, stat: SPECIALEnum = SPECIALEnum.STRENGTH) -> Dweller:
    return Dweller(**{stat.value.lower(): value}, apprentice_stat=stat)


def _outfitted_workers(stat: str, count: int) -> list[Dweller]:
    """Boosted stat-5 workers wearing the Common +3 outfit the seed equips them with (effective 8)."""
    outfit = build_outfit({"name": f"seed {stat} outfit", stat: 3}, RarityEnum.COMMON)
    return [Dweller(**{stat: 5, "outfit": outfit}) for _ in range(count)]


async def _prepared(is_boosted: bool):
    from uuid import uuid4

    from app.core.game_data import get_static_game_data
    from app.services.vault import seeding

    return seeding.prepare_initial_rooms((await get_static_game_data()).rooms, uuid4(), is_boosted=is_boosted)


@pytest.mark.asyncio
async def test_seeded_vault_live_power_and_food_hold_when_staffed() -> None:
    standard = await _prepared(is_boosted=False)
    assert _seeded_net(standard, 10, [_adults(5, 2)], "power", "power") > 0
    assert _seeded_net(standard, 10, [_adults(5, 0)], "power", "power") < 0

    prepared = await _prepared(is_boosted=True)
    generators = [room for room in prepared.production if str(room.name).lower().startswith("power")]
    assert len(generators) == 1  # seeded directly at final size, no fusion round-trip
    assert (generators[0].size, generators[0].output) == (6, 70)  # (2*6*(2+4))-2 at tier 2, size 6

    full = [[*_outfitted_workers("strength", 5), _apprentice(5)]]
    assert _seeded_net(prepared, 33, full, "power", "power") > 75
    # A two-worker shed stays safe; one worker left is the depth at which the big boosted draw wins.
    two_left = [[*_outfitted_workers("strength", 2), _apprentice(5)]]
    assert _seeded_net(prepared, 33, two_left, "power", "power") > 0
    one_left = [[*_outfitted_workers("strength", 1), _apprentice(5)]]
    assert _seeded_net(prepared, 33, one_left, "power", "power") > 0
    assert _seeded_net(prepared, 33, [[_apprentice(5)]], "power", "power") < 0

    diner_crew = [*_outfitted_workers("agility", 2), _apprentice(5, SPECIALEnum.AGILITY)]
    assert _seeded_net(prepared, 33, [diner_crew], "food", "diner") > 0


def test_friction_multiplier_penalizes_discomfort_and_rivals() -> None:
    human, peer = Dweller(strength=5), Dweller(strength=5)
    human.visual_attributes = peer.visual_attributes = {"race": "human"}
    feral = Dweller(strength=5)
    feral.visual_attributes = {"race": "ghoul", "state_of_being": "feral"}
    mutant = Dweller(strength=5)
    mutant.visual_attributes = {"race": "super_mutant"}

    assert ResourceManager._friction_multiplier([human, peer], None) == 1.0
    assert ResourceManager._friction_multiplier([human, feral], None) == pytest.approx(
        DISCOMFORT_EFFECTS[DiscomfortSeverity.STRONG].production_multiplier
    )

    rival_pairs = {frozenset((human.id, mutant.id))}
    penalty = game_config.relationship.rival_production_penalty
    expected = max(
        DISCOMFORT_PRODUCTION_FLOOR,
        DISCOMFORT_EFFECTS[DiscomfortSeverity.MODERATE].production_multiplier * max(1 - 2 * penalty, 1 - penalty),
    )
    assert ResourceManager._friction_multiplier([human, mutant], rival_pairs) == pytest.approx(expected)
