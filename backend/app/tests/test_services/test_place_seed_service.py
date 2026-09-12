"""Tests for the canonical place seed loader."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PlaceKindEnum
from app.models.world_location import WorldLocation
from app.services.place_seed_service import (
    get_origin_places,
    get_visited_places,
    load_seed_entries,
    seed_places_from_json,
)


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
