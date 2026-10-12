from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cli.simulate_resources import ResourceEconomyConfig, simulate
from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.crud import room as room_crud
from app.crud.resource import VaultResourceData
from app.models import Dweller, Storage
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.schemas.vault import ResourceLevelWarning, ResourceProduction, ResourceTickEvents
from app.services.resource_manager import ResourceManager
from app.utils.item_factory import build_outfit
from app.utils.resource_warnings import get_resource_warnings


class TestResourceManager:
    def test_check_resource_warnings(self):
        vault = Vault(power_max=100, food_max=100, water_max=100)

        # Test normal levels
        resources = {"power": 50.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 0

        # Test low power (19%)
        resources = {"power": 19.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 1
        assert isinstance(warnings[0], ResourceLevelWarning)
        assert warnings[0].type == "low_power"

        # Test critical power (4%)
        resources = {"power": 4.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 1
        assert warnings[0].type == "critical_power"

        # Test multiple warnings
        resources = {"power": 4.0, "food": 19.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 2
        types = [warning.type for warning in warnings]
        assert "critical_power" in types
        assert "low_food" in types

    def test_zero_water_emits_dehydration_instead_of_critical_water(self):
        vault = Vault(power_max=100, food_max=100, water_max=100)

        resources = {"power": 50.0, "food": 50.0, "water": 0.0}
        warnings = get_resource_warnings(vault, resources)
        types = [warning.type for warning in warnings]
        assert "critical_water" not in types
        assert "critical_dehydration" in types

    @pytest.mark.asyncio
    async def test_power_outage_production(self):
        manager = ResourceManager()

        # Create mock rooms
        power_room = Room(
            name="Power", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, output=10.0, tier=1, size=1
        )
        food_room = Room(
            name="Diner", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.AGILITY, output=10.0, tier=1, size=1
        )

        from app.models.dweller import Dweller

        strong_dweller = Dweller(strength=10)
        agile_dweller = Dweller(agility=10)

        rooms_with_dwellers = [(power_room, [strong_dweller]), (food_room, [agile_dweller])]

        # Scenario 1: Sufficient Power
        production_normal = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=10)
        assert production_normal["power"] > 0
        assert production_normal["food"] > 0

        # Scenario 2: Power Outage
        production_outage = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=0)
        assert production_outage["power"] > 0  # Power plants still work
        assert production_outage["food"] == 0  # Diners stop working

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("starting_stimpacks", "capacity", "output", "expected_delta"), [(4, 5, 33, 1), (5, 5, 100, 0)]
    )
    async def test_medical_events_match_persisted_storage_change(
        self, vault: Vault, starting_stimpacks: int, capacity: int, output: int, expected_delta: int
    ) -> None:
        """Medical collection events must match rounded, capacity-limited storage changes."""
        vault.power = 10
        storage = Storage(vault_id=vault.id, stimpack=starting_stimpacks)
        medbay = Room(
            name="Medbay",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.INTELLIGENCE,
            output=output,
            capacity=capacity,
            tier=1,
            size=1,
        )
        resource_data = VaultResourceData(
            vault=vault,
            storage=storage,
            rooms=[medbay],
            dweller_count=0,
            rooms_with_dwellers=[(medbay, [Dweller(intelligence=1)])],
        )

        with (
            patch(
                "app.services.resource_manager.resource_crud.get_vault_resource_data",
                new_callable=AsyncMock,
                return_value=resource_data,
            ),
            patch("app.services.resource_manager.event_bus.emit", new_callable=AsyncMock) as emit,
        ):
            _, events = await ResourceManager().process_vault_resources(MagicMock(), vault.id, 60)
            await ResourceManager.emit_production_events(vault.id, events)

        medical_amounts = [
            call.args[2]["amount"] for call in emit.await_args_list if call.args[2]["resource_type"] == "stimpack"
        ]
        assert storage.stimpack == starting_stimpacks + expected_delta
        assert medical_amounts == ([expected_delta] if expected_delta else [])

    @pytest.mark.asyncio
    async def test_junior_worker_assists_production_at_the_reduced_rate(self):
        """A youth posted to a production room adds production at the junior reduced rate."""
        from app.core.enums import AgeGroupEnum

        manager = ResourceManager()
        room = Room(
            name="Power",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            output=10.0,
            tier=1,
            size=1,
        )
        adult = Dweller(strength=10)
        junior = Dweller(strength=10, age_group=AgeGroupEnum.TEEN, apprentice_stat=SPECIALEnum.STRENGTH)

        adult_only = manager._calculate_production([(room, [adult])], seconds_passed=60, current_power=10)["power"]
        with_junior = manager._calculate_production([(room, [adult, junior])], seconds_passed=60, current_power=10)[
            "power"
        ]

        assert adult_only > 0
        assert with_junior == pytest.approx(adult_only * (1 + game_config.resource.junior_worker_output_multiplier))


# Slice 3b contract source: docs/features/RESOURCE_ECONOMY_BALANCE.md. The
# shipped default moved to 0.0012 with the live-tuned correction
# (docs/backend/BALANCE_PLAYTEST.md Slice 3b §10).
STARTER_ROOM_OUTPUT = 28  # catalog output (2*S*(L+4))-2 at tier 1, size 3


def test_base_production_rate_default_matches_resource_economy_baseline() -> None:
    """The shipped default reproduces the documented per-tick starts across staffing states."""
    assert game_config.resource.base_production_rate == pytest.approx(0.0012)


@pytest.mark.parametrize(
    ("workers_per_room", "expected_net_per_tick"),
    [
        (2, {"power": 16, "food": 17, "water": 17}),
        (1, {"power": 6, "food": 7, "water": 7}),
        (0, {"power": -4, "food": -3, "water": -3}),
    ],
)
def test_starter_vault_meets_resource_economy_baseline_contract(
    workers_per_room: int, expected_net_per_tick: dict[str, int]
) -> None:
    """The simulator's three-production-room model at the shipped rate (live all-room draw lives in §10)."""
    result = simulate(
        ResourceEconomyConfig(
            population=9,
            workers_per_room=workers_per_room,
            worker_special=5,
            room_tier=1,
            room_size=3,
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
        Room(
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            output=float(STARTER_ROOM_OUTPUT),
            tier=1,
            size=3,
        ),
        Room(
            name="Diner",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.AGILITY,
            output=float(STARTER_ROOM_OUTPUT),
            tier=1,
            size=3,
        ),
        Room(
            name="Water Treatment",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.PERCEPTION,
            output=float(STARTER_ROOM_OUTPUT),
            tier=1,
            size=3,
        ),
    ]
    rooms_with_dwellers = [
        (rooms[0], [Dweller(strength=5), Dweller(strength=5)]),
        (rooms[1], [Dweller(agility=5), Dweller(agility=5)]),
        (rooms[2], [Dweller(perception=5), Dweller(perception=5)]),
    ]
    offline = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=vault.power)
    resource_data = VaultResourceData(
        vault=vault,
        storage=None,
        rooms=rooms,
        dweller_count=9,
        rooms_with_dwellers=rooms_with_dwellers,
    )

    with (
        patch(
            "app.services.resource_manager.resource_crud.get_vault_resource_data",
            new_callable=AsyncMock,
            return_value=resource_data,
        ),
        patch("app.services.resource_manager.event_bus.emit", new_callable=AsyncMock),
    ):
        _, events = await manager.process_vault_resources(MagicMock(), vault.id, 60)

    for resource in ("power", "food", "water"):
        assert getattr(events.production, resource) == pytest.approx(offline[resource])


def test_offline_single_step_window_diverges_from_per_tick_rounding() -> None:
    """Offline catch-up runs one 3600 s window; per-tick stepping accumulates per-tick integer rounding."""
    from app.cli.simulate_resources import _build_scenario

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
    manager = ResourceManager()
    consumption = manager._calculate_consumption(rooms, cfg.population, 3600)
    production = manager._calculate_production(rooms_with_dwellers, 3600, vault.power)
    single_step_power = round(manager._apply_resource_changes(vault, consumption, production)["power"])
    per_tick_power = simulate(cfg).final_resources["power"]
    assert single_step_power < per_tick_power


def _seeded_net(
    prepared,
    dweller_count: int,
    crews: list[list[Dweller]],
    resource: str,
    room_prefix: str,
    production: list[RoomCreate] | None = None,
) -> float:
    """Net live per-minute change for one resource over the real seeded room set."""
    manager = ResourceManager()
    production_rooms = production if production is not None else prepared.production
    rooms = [
        *prepared.infrastructure,
        *prepared.capacity,
        *production_rooms,
        *prepared.misc,
        *prepared.training,
        *prepared.arena,
        *prepared.crafting,
    ]
    matched = [room for room in production_rooms if str(room.name).lower().startswith(room_prefix)]
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


@pytest.mark.asyncio
async def test_seeded_standard_vault_live_power_survives_when_staffed_and_deficits_on_one_worker() -> None:
    """All-room draw (14/min), not the simulator's three rooms, is the live starter tripwire (§10)."""
    from uuid import uuid4

    from app.core.game_data import get_static_game_data
    from app.services.vault import seeding

    prepared = seeding.prepare_initial_rooms((await get_static_game_data()).rooms, uuid4(), is_boosted=False)

    assert _seeded_net(prepared, 10, [_adults(5, 2)], "power", "power") > 0
    assert _seeded_net(prepared, 10, [_adults(5, 1)], "power", "power") < 0


@pytest.mark.asyncio
async def test_seeded_boosted_vault_size_six_generator_keeps_live_power_positive_with_margin() -> None:
    """The seeded size-6 generator's outfitted double crew nets a large margin; a deep shed still flips negative."""
    from uuid import uuid4

    from app.core.game_data import get_static_game_data
    from app.services.vault import seeding

    prepared = seeding.prepare_initial_rooms((await get_static_game_data()).rooms, uuid4(), is_boosted=True)
    production = [room for room in prepared.production if str(room.name).lower().startswith("power")]

    assert len(production) == 1  # seeded directly at final size, no fusion round-trip
    assert production[0].size == 6
    assert production[0].output == 58  # (2*6*(1+4))-2 at tier 1, size 6

    full = [[*_outfitted_workers("strength", 5), _apprentice(5)]]
    assert _seeded_net(prepared, 33, full, "power", "power", production=production) > 100
    # A two-worker shed stays safe; one worker left is the depth at which the big boosted draw wins.
    two_left = [[*_outfitted_workers("strength", 2), _apprentice(5)]]
    assert _seeded_net(prepared, 33, two_left, "power", "power", production=production) > 0
    one_left = [[*_outfitted_workers("strength", 1), _apprentice(5)]]
    assert _seeded_net(prepared, 33, one_left, "power", "power", production=production) < 0


@pytest.mark.asyncio
async def test_seeded_boosted_diner_outfitted_crew_keeps_live_food_positive() -> None:
    """The diner's two outfitted AGI workers plus the seeded teen out-produce the boosted food draw."""
    from uuid import uuid4

    from app.core.game_data import get_static_game_data
    from app.services.vault import seeding

    prepared = seeding.prepare_initial_rooms((await get_static_game_data()).rooms, uuid4(), is_boosted=True)
    diner_crew = [*_outfitted_workers("agility", 2), _apprentice(5, SPECIALEnum.AGILITY)]
    assert _seeded_net(prepared, 33, [diner_crew], "food", "diner") > 0
