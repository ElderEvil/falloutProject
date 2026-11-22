"""Balance wave 3 (issue #1456): seeded-layout rate gates.

These tests are the release gate for the retuned rates. They seed the real starter layouts through the
production seeding path, then measure one 60-second resource window with the live ResourceManager formulas,
so the numbers cannot drift from the catalog or the crew the seeds actually place.

The issue's "one worker sustains 8.7 dwellers" is superseded: the boosted diner seats three crew but one slot
is a half-rate apprentice, so it is the binding case. Rates are set so both seeds stay net-positive; the
scarcity lever is the stock buffer, documented in docs/backend/BALANCE_WAVE_3.md.
"""

import pytest

from app import crud
from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.crud.resource import resource
from app.options.identity_modifiers import effective_stat
from app.services.resource_manager_service import ResourceManager
from app.services.vault import seeding

RESOURCES = ("power", "food", "water")


async def _seed_layout(async_session, vault, boosted: bool):
    """Seed the real starter layout (rooms, storage, dwellers) and return its resource data."""
    game_data = await get_static_game_data()
    prepared = seeding.prepare_initial_rooms(game_data.rooms, vault.id, is_boosted=boosted)
    await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    _vault_obj, created = await seeding.create_initial_rooms(async_session, vault, prepared)
    await seeding.create_initial_dwellers(
        async_session,
        vault.id,
        created.production,
        created.training,
        created.misc,
        created.capacity,
        is_boosted=boosted,
        created_crafting_rooms=created.crafting,
    )
    await async_session.commit()
    return await resource.get_vault_resource_data(async_session, vault.id)


def _net_per_minute(model, data, crew_special: int) -> dict[str, float]:
    """Run one 60-second window from 20 % stock and return the net change per resource.

    Seeding rolls random SPECIAL and outfits, so each worker's effective stat is pinned here: the rate
    contract is about the layout and the crew shape, never about which stats the seed happened to roll.
    """
    for room, crew in data.rooms_with_dwellers:
        if room.ability is None:
            continue
        stat = room.ability.value.lower()
        for dweller in crew:
            setattr(dweller, stat, getattr(dweller, stat) + (crew_special - effective_stat(dweller, stat)))

    for name in RESOURCES:
        setattr(model, name, getattr(model, f"{name}_max") * 0.2)
    before = {name: getattr(model, name) for name in RESOURCES}
    update, _events = ResourceManager().calculate_resource_window(
        model,
        data.rooms,
        data.dweller_count,
        data.rooms_with_dwellers,
        60,
        state=data.game_state,
    )
    return {name: getattr(update, name) - before[name] for name in RESOURCES}


def _power_draw_per_minute(data) -> float:
    """Seeded draw: every room draws by size and tier."""
    units = sum((room.size or 0) * (room.tier or 1) for room in data.rooms)
    return units * game_config.resource.power_consumption_rate * 60


@pytest.mark.asyncio
@pytest.mark.parametrize("boosted", [False, True], ids=["standard", "boosted"])
async def test_seeded_layout_is_net_positive_for_food_and_water(async_session, vault, boosted: bool) -> None:
    """Both seeds must not starve at the shipped rates; a paid boosted start must clear its draw."""
    data = await _seed_layout(async_session, vault, boosted)
    net = _net_per_minute(data.vault, data, 8 if boosted else 5)

    assert net["food"] >= 0, f"seeded {boosted=} food net {net['food']}/min is negative"
    assert net["water"] >= 0, f"seeded {boosted=} water net {net['water']}/min is negative"


@pytest.mark.asyncio
async def test_standard_seed_power_surplus_stays_inside_the_band(async_session, vault) -> None:
    """The standard seed is the binding power case: 1.25-1.55x surplus, no more."""
    data = await _seed_layout(async_session, vault, boosted=False)
    net = _net_per_minute(data.vault, data, 5)
    draw = _power_draw_per_minute(data)
    ratio = (net["power"] + draw) / draw

    assert 1.25 <= ratio <= 1.55, f"standard power surplus {ratio:.2f}x outside the tuned band"


@pytest.mark.asyncio
async def test_boosted_seed_stays_power_rich_by_design(async_session, vault) -> None:
    """A boosted start is a paid head start: it must clear 1.15x, with no upper bound."""
    data = await _seed_layout(async_session, vault, boosted=True)
    net = _net_per_minute(data.vault, data, 8)
    draw = _power_draw_per_minute(data)
    ratio = (net["power"] + draw) / draw

    assert ratio >= 1.15, f"boosted power surplus {ratio:.2f}x below the floor"
