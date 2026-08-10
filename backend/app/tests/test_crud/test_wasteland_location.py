"""Tests for CRUDWastelandLocation — unlock_places_for_dweller and get_dweller_refs."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.wasteland_location import wasteland_location as wl_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation, DwellerLocationRelationEnum


@pytest.mark.asyncio
async def test_unlock_places_for_dweller_updates_rows(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """unlock_places_for_dweller sets is_unlocked=True on all DwellerLocation rows for the dweller."""
    # Create a location and link it to the dweller
    from app.models.wasteland_location import LocationTypeEnum, WastelandLocation

    loc = WastelandLocation(
        name="Megaton",
        normalized_name="megaton",
        type=LocationTypeEnum.ORIGIN,
        coord_x=30.0,
        coord_y=40.0,
        description="Test",
        vault_id=vault.id,
    )
    async_session.add(loc)
    await async_session.flush()

    link = DwellerLocation(
        dweller_id=dweller.id,
        location_id=loc.id,
        relation=DwellerLocationRelationEnum.ORIGIN,
    )
    async_session.add(link)
    await async_session.commit()

    # Verify initial state: is_unlocked is False
    await async_session.refresh(link)
    assert link.is_unlocked is False

    # Unlock
    updated = await wl_crud.unlock_places_for_dweller(async_session, dweller_id=dweller.id)
    assert updated == 1

    # Verify is_unlocked is now True
    await async_session.refresh(link)
    assert link.is_unlocked is True


@pytest.mark.asyncio
async def test_unlock_places_for_dweller_no_rows(async_session: AsyncSession, vault: Vault) -> None:
    """unlock_places_for_dweller returns 0 when the dweller has no linked places."""
    from uuid import uuid4

    updated = await wl_crud.unlock_places_for_dweller(async_session, dweller_id=uuid4())
    assert updated == 0


@pytest.mark.asyncio
async def test_get_dweller_refs_includes_is_unlocked(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_dweller_refs returns is_unlocked in each dweller ref dict."""
    from app.models.wasteland_location import LocationTypeEnum, WastelandLocation

    loc = WastelandLocation(
        name="Rivet City",
        normalized_name="rivet_city",
        type=LocationTypeEnum.VISITED,
        coord_x=60.0,
        coord_y=50.0,
        description="Test",
        vault_id=vault.id,
    )
    async_session.add(loc)
    await async_session.flush()

    link = DwellerLocation(
        dweller_id=dweller.id,
        location_id=loc.id,
        relation=DwellerLocationRelationEnum.VISITED,
    )
    async_session.add(link)
    await async_session.commit()

    refs_map = await wl_crud.get_dweller_refs(async_session, [loc.id])
    refs = refs_map.get(loc.id, [])
    assert len(refs) == 1
    assert refs[0]["dweller_id"] == dweller.id
    assert refs[0]["is_unlocked"] is False
    assert "is_unlocked" in refs[0]
