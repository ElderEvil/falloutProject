"""Tests for CRUDWastelandLocation race-safe CRUD operations."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.wasteland_location import wasteland_location as wl_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation, DwellerLocationRelationEnum, WastelandLocation


@pytest.mark.asyncio
async def test_get_or_create_creates_new(async_session: AsyncSession, vault: Vault) -> None:
    """A new location is created; a differently-cased version reuses the same row."""
    loc1 = await wl_crud.get_or_create(async_session, vault.id, "Megaton", "origin", description="Test origin")
    assert loc1 is not None
    assert loc1.normalized_name == "megaton"
    assert loc1.type == "origin"

    # Second call with different casing — must return the SAME row
    loc2 = await wl_crud.get_or_create(async_session, vault.id, " MEGATON ", "origin")
    assert loc2.id == loc1.id
    assert loc2.normalized_name == "megaton"


@pytest.mark.asyncio
async def test_get_or_create_simulated_race(async_session: AsyncSession, vault: Vault) -> None:
    """Simulate a race: get_by_normalized returns None, insert hits IntegrityError,
    rollback + re-select returns the existing row."""
    # Create a location directly so the DB unique constraint exists.
    normalized = "racetown"
    pre_existing = WastelandLocation(
        name="Racetown",
        normalized_name=normalized,
        type="visited",
        coord_x=42.0,
        coord_y=42.0,
        vault_id=vault.id,
    )
    async_session.add(pre_existing)
    await async_session.commit()
    await async_session.refresh(pre_existing)
    pre_existing_id = pre_existing.id  # capture before rollback expels it

    # Now call get_or_create.  First call to get_by_normalized → None (simulates
    # a concurrent thread that didn't see the row yet).  Second call (inside the
    # IntegrityError handler) returns the pre-existing row.
    with patch.object(wl_crud, "get_by_normalized", side_effect=[None, pre_existing]) as mock_fn:
        result = await wl_crud.get_or_create(async_session, vault.id, "Racetown", "visited")
        assert result is not None
        await async_session.refresh(result)
        assert result.id == pre_existing_id
        assert mock_fn.call_count == 2


@pytest.mark.asyncio
async def test_link_dweller_idempotent(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Linking the same dweller to the same location twice yields 1 link row."""
    loc = await wl_crud.get_or_create(async_session, vault.id, "Megaton", "origin")

    link1 = await wl_crud.link_dweller(async_session, dweller.id, loc.id, DwellerLocationRelationEnum.ORIGIN)
    assert link1 is not None

    # Second call with the same args — must not raise and must return the same link
    link2 = await wl_crud.link_dweller(async_session, dweller.id, loc.id, DwellerLocationRelationEnum.ORIGIN)
    assert link2.id == link1.id

    # Verify exactly one row in DB
    result = await async_session.execute(
        select(DwellerLocation).where(
            DwellerLocation.dweller_id == dweller.id,
            DwellerLocation.location_id == loc.id,
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_dweller_refs_batch(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Batch query returns dweller refs for multiple location ids in one query."""
    loc1 = await wl_crud.get_or_create(async_session, vault.id, "Rivet City", "visited")
    loc2 = await wl_crud.get_or_create(async_session, vault.id, "Megaton", "visited")

    await wl_crud.link_dweller(async_session, dweller.id, loc1.id, DwellerLocationRelationEnum.VISITED)
    await wl_crud.link_dweller(async_session, dweller.id, loc2.id, DwellerLocationRelationEnum.VISITED)

    mapping = await wl_crud.get_dweller_refs(async_session, [loc1.id, loc2.id])
    assert len(mapping[loc1.id]) == 1
    assert mapping[loc1.id][0]["dweller_id"] == dweller.id
    assert mapping[loc1.id][0]["first_name"] == dweller.first_name
    assert mapping[loc1.id][0]["relation"] == "visited"
    assert len(mapping[loc2.id]) == 1


@pytest.mark.asyncio
async def test_get_by_vault(async_session: AsyncSession, vault: Vault) -> None:
    """List all locations scoped to a vault."""
    await wl_crud.get_or_create(async_session, vault.id, "Megaton", "visited")
    await wl_crud.get_or_create(async_session, vault.id, "Rivet City", "discovery")

    rows = await wl_crud.get_by_vault(async_session, vault.id)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_get_by_normalized(async_session: AsyncSession, vault: Vault) -> None:
    """Find a location by vault + normalized name."""
    await wl_crud.get_or_create(async_session, vault.id, "Megaton", "visited")
    found = await wl_crud.get_by_normalized(async_session, vault.id, "megaton")
    assert found is not None
    assert found.name == "Megaton"

    missing = await wl_crud.get_by_normalized(async_session, vault.id, "nope")
    assert missing is None


@pytest.mark.asyncio
async def test_get_by_id(async_session: AsyncSession, vault: Vault) -> None:
    """Find a location by its primary key."""
    loc = await wl_crud.get_or_create(async_session, vault.id, "Megaton", "visited")
    found = await wl_crud.get_by_id(async_session, loc.id)
    assert found is not None
    assert found.id == loc.id

    missing = await wl_crud.get_by_id(async_session, uuid4())
    assert missing is None
