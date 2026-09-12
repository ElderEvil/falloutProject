"""Tests for BioPlaceBackfillService."""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.world_location import VaultLocationState
from app.services.bio_place_backfill_service import bio_place_backfill_service, extract_places_from_bio
from app.services.map_service import map_service

# ---------------------------------------------------------------------------
# extract_places_from_bio unit tests
# ---------------------------------------------------------------------------


def test_extract_no_bio_returns_none_empty() -> None:
    """No bio -> no origin, no visited."""
    origin, visited = extract_places_from_bio(None)
    assert origin is None
    assert visited == []


# ---------------------------------------------------------------------------
# BioPlaceBackfillService integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_bio_places_for_vault_respects_max_dwellers(async_session: AsyncSession, vault: Vault) -> None:
    """max_dwellers limits how many dwellers are processed."""
    from app.schemas.common import GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    for i in range(3):
        data = {
            "first_name": f"Dweller{i}",
            "last_name": "Test",
            "gender": GenderEnum.MALE,
            "rarity": RarityEnum.COMMON,
            "level": 1,
            "bio": "Originally from Megaton, they scavenged the Capital Wasteland.",
        }
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))

    processed = await bio_place_backfill_service.backfill_bio_places_for_vault(async_session, vault.id, max_dwellers=2)

    assert processed == 2


@pytest.mark.asyncio
async def test_backfill_bio_places_for_active_vaults_skips_deleted(async_session: AsyncSession) -> None:
    """Only non-deleted vaults are backfilled."""
    from faker import Faker

    from app.schemas.common import GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID

    fake = Faker()

    async def _make_vault(number: int, deleted: bool) -> Vault:
        user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
        user = await crud.user.create(db_session=async_session, obj_in=user_in)
        vault_data = {
            "number": number,
            "bottle_caps": 1000,
            "happiness": 50,
            "power": 10,
            "food": 10,
            "water": 10,
            "population_max": 50,
        }
        vault = await crud.vault.create(
            db_session=async_session,
            obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id),
        )
        if deleted:
            vault.is_deleted = True
            async_session.add(vault)
            await async_session.commit()
        return vault

    active_vault = await _make_vault(100, deleted=False)
    deleted_vault = await _make_vault(101, deleted=True)

    for target_vault in (active_vault, deleted_vault):
        data = {
            "first_name": "Backfill",
            "last_name": "Candidate",
            "gender": GenderEnum.MALE,
            "rarity": RarityEnum.COMMON,
            "level": 1,
            "bio": "Originally from Megaton, they scavenged the Capital Wasteland.",
        }
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**data, vault_id=target_vault.id))

    counts = await bio_place_backfill_service.backfill_bio_places_for_active_vaults(async_session)

    assert counts == {active_vault.id: 1}

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    assert all(r.vault_id == active_vault.id for r in rows)
