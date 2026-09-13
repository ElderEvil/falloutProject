"""Tests for the canonical place seed loader."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PlaceKindEnum
from app.models.world_location import WorldLocation
from app.services.place_seed_service import (
    get_origin_places,
    get_visited_places,
    seed_places_from_json,
)
from app.utils.place_seed import load_seed_entries


@pytest.mark.asyncio
async def test_seed_inserts_roster_and_is_idempotent(async_session: AsyncSession) -> None:
    """First run inserts every entry; a second run inserts nothing."""
    first = await seed_places_from_json(async_session, commit=False)
    assert first == len(load_seed_entries())
    second = await seed_places_from_json(async_session, commit=False)
    assert second == 0


@pytest.mark.asyncio
async def test_seeded_vault_rows_match_roster(async_session: AsyncSession) -> None:
    """Seeded VAULT rows reproduce the roster exactly (name, number, coords)."""
    await seed_places_from_json(async_session, commit=False)
    rows = (
        (
            await async_session.execute(
                select(WorldLocation).where(WorldLocation.kind == PlaceKindEnum.VAULT, WorldLocation.source == "seed")
            )
        )
        .scalars()
        .all()
    )
    expected = [entry for entry in load_seed_entries() if entry["kind"] == "vault"]
    assert len(rows) == len(expected)
    by_name = {row.name: row for row in rows}
    for entry in expected:
        row = by_name[entry["name"]]
        assert row.vault_number == entry["vault_number"]
        assert (row.coord_x, row.coord_y) == (entry["coord_x"], entry["coord_y"])


def test_seed_covers_known_bio_places() -> None:
    """Core bio names resolve through the seed-driven lists."""
    assert "Megaton" in get_origin_places()
    assert "Megaton" in get_visited_places()
    assert "Nuka-Cola Plant" in get_visited_places()


@pytest.mark.asyncio
async def test_seed_conflict_rolls_back_only_that_entry(async_session: AsyncSession) -> None:
    """A conflicting seed insert must not discard previously seeded rows."""
    from unittest.mock import patch

    from app.crud.world_location import world_location as wl_crud

    await seed_places_from_json(async_session, commit=False)
    await async_session.commit()
    before = len((await async_session.execute(select(WorldLocation))).scalars().all())

    real_lookup = wl_crud.get_registry_by_normalized
    megaton = await real_lookup(async_session, "megaton")
    assert megaton is not None
    missed_once = False

    async def miss_megaton_once(db_session, normalized):
        nonlocal missed_once
        if normalized == "megaton" and not missed_once:
            missed_once = True
            return None
        return await real_lookup(db_session, normalized)

    with patch.object(wl_crud, "get_registry_by_normalized", new=miss_megaton_once):
        inserted = await seed_places_from_json(async_session, commit=False)
    assert missed_once, "expected the forced fast-path miss to trigger"
    assert inserted == 0
    after = len((await async_session.execute(select(WorldLocation))).scalars().all())
    assert after == before


@pytest.mark.asyncio
async def test_seeded_places_carry_their_group(async_session: AsyncSession) -> None:
    """Seeded rows get their group key, and instances of a chain share it."""
    await seed_places_from_json(async_session, commit=False)
    rows = (
        (await async_session.execute(select(WorldLocation).where(WorldLocation.kind == PlaceKindEnum.PLACE)))
        .scalars()
        .all()
    )
    by_name = {row.name: row for row in rows}
    assert by_name["Red Rocket"].group_key == "gas_station"
    assert by_name["Red Rocket - Springvale"].group_key == by_name["Red Rocket"].group_key
    assert by_name["Super Duper Mart"].group_key == "supermarket"


@pytest.mark.asyncio
async def test_emergent_place_resolves_seeded_group(async_session: AsyncSession) -> None:
    """A known name registered emergently still inherits its group."""
    from app.crud.world_location import world_location as wl_crud

    location = await wl_crud.get_or_create_location(async_session, "Red Rocket")
    assert location.group_key == "gas_station"


@pytest.mark.asyncio
async def test_reseed_backfills_group_on_existing_rows(async_session: AsyncSession) -> None:
    """A row that predates the taxonomy gets its group on the next seed run, whatever its source."""
    from app.crud.world_location import world_location as wl_crud

    await seed_places_from_json(async_session, commit=False)
    red_rocket = await wl_crud.get_registry_by_normalized(async_session, "red rocket")
    assert red_rocket is not None
    red_rocket.group_key = None
    red_rocket.source = "emergent"
    async_session.add(red_rocket)
    await async_session.flush()

    await seed_places_from_json(async_session, commit=False)
    await async_session.flush()

    await async_session.refresh(red_rocket)
    assert red_rocket.group_key == "gas_station"


@pytest.mark.asyncio
async def test_seed_rejects_unknown_group(async_session: AsyncSession, monkeypatch) -> None:
    """A seed entry whose group is not in the catalog fails before any write."""
    from app.crud.world_location import world_location as wl_crud
    from app.services import place_seed_service

    bad = [{"name": "Nowhere Gulch", "kind": "place", "description": None, "roles": [], "group": "not_a_group"}]
    monkeypatch.setattr(place_seed_service, "load_seed_entries", lambda: bad)

    with pytest.raises(ValueError, match="Unknown place group"):
        await seed_places_from_json(async_session, commit=False)

    assert await wl_crud.get_registry_by_normalized(async_session, "nowhere gulch") is None
