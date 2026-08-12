"""Tests for BioPlaceBackfillService."""

from __future__ import annotations

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation, WastelandLocation
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


def test_extract_empty_bio_returns_none_empty() -> None:
    """Empty bio string -> no matches."""
    origin, visited = extract_places_from_bio("")
    assert origin is None
    assert visited == []


def test_extract_bio_with_no_known_places() -> None:
    """Bio text without any known place mentions -> skipped, no crash."""
    origin, visited = extract_places_from_bio(
        "This dweller came from a small outpost and never went anywhere notable."
    )
    assert origin is None
    assert visited == []


def test_extract_origin_place_from_bio() -> None:
    """Bio containing a known origin place name is extracted."""
    origin, visited = extract_places_from_bio("Originally from Megaton, this dweller learned to survive early.")
    assert origin == "Megaton"
    assert visited == []


def test_extract_visited_place_from_bio() -> None:
    """Bio containing a known visited place name is extracted."""
    origin, visited = extract_places_from_bio("They once scavenged the Capital Wasteland and lived to tell the tale.")
    assert origin is None
    assert "the Capital Wasteland" in visited


def test_extract_origin_and_visited_from_bio() -> None:
    """Bio with both origin and visited places -> both extracted."""
    origin, visited = extract_places_from_bio(
        "Hailing from Diamond City, this dweller wandered through the Commonwealth and survived a trip to Far Harbor."
    )
    assert origin == "Diamond City"
    assert "the Commonwealth" in visited
    assert "Far Harbor" in visited


def test_extract_multi_word_place() -> None:
    """Multi-word places like Starlight Drive-In are matched correctly."""
    origin, visited = extract_places_from_bio(
        "They set up a trading post near Starlight Drive-In after leaving Sanctuary Hills."
    )
    assert origin == "Sanctuary Hills"
    assert "Starlight Drive-In" in visited


def test_extract_case_insensitive() -> None:
    """Place matching is case-insensitive."""
    origin, visited = extract_places_from_bio("born in megaton, travelled to the commonwealth.")
    assert origin == "Megaton"
    assert "the Commonwealth" in visited


def test_extract_does_not_match_partial_words() -> None:
    """Regex word-boundary: 'Megaton' does NOT match inside 'Megatonia'."""
    origin, visited = extract_places_from_bio(
        "The Megatonia settlement was prosperous but nothing like Megaton itself."
    )
    assert origin == "Megaton"
    assert visited == []


def test_extract_visited_with_leading_space_in_list() -> None:
    """Places like ' Zion Canyon' (with leading space in visited list) match in bio text."""
    origin, visited = extract_places_from_bio("They survived Zion Canyon and brought back useful herbs.")
    assert origin is None
    assert "Zion Canyon" in visited


def test_extract_place_in_both_lists_treated_as_origin() -> None:
    """Places in both origin and visited lists -> treated as origin, not duplicated."""
    origin, visited = extract_places_from_bio(
        "From Sanctuary Hills, they dreamed of returning to Sanctuary Hills one day."
    )
    assert origin == "Sanctuary Hills"
    assert "Sanctuary Hills" not in visited


def test_extract_multiple_visited_deduped() -> None:
    """Repeated place mentions -> deduplicated in visited list."""
    origin, visited = extract_places_from_bio("They went to Far Harbor, then Far Harbor again, and also Far Harbor.")
    assert origin is None
    assert visited == ["Far Harbor"]


# ---------------------------------------------------------------------------
# BioPlaceBackfillService integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_bio_places_for_vault_registers_missing(
    async_session: AsyncSession, vault: Vault
) -> None:
    """Dwellers with bio but no locations are registered; linked dwellers are skipped."""
    from app.schemas.common import GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    missing_data = {
        "first_name": "Missing",
        "last_name": "Map",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "level": 1,
        "bio": "Originally from Megaton, they scavenged the Capital Wasteland.",
    }
    await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**missing_data, vault_id=vault.id)
    )

    linked_data = {
        "first_name": "Already",
        "last_name": "Mapped",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "level": 1,
        "bio": "From Diamond City, they explored Far Harbor.",
    }
    linked = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**linked_data, vault_id=vault.id)
    )
    await map_service.register_bio_places(
        async_session, linked, origin_place="Diamond City", visited_places=[]
    )
    await async_session.commit()

    processed = await bio_place_backfill_service.backfill_bio_places_for_vault(async_session, vault.id)

    assert processed == 1

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    names = {r.name for r in rows}
    assert "Megaton" in names
    assert "the Capital Wasteland" in names
    assert "Diamond City" in names

    links = (
        await async_session.execute(select(DwellerLocation).where(DwellerLocation.dweller_id == linked.id))
    ).scalars().all()
    assert len(links) == 1


@pytest.mark.asyncio
async def test_backfill_bio_places_for_vault_respects_max_dwellers(
    async_session: AsyncSession, vault: Vault
) -> None:
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

    processed = await bio_place_backfill_service.backfill_bio_places_for_vault(
        async_session, vault.id, max_dwellers=2
    )

    assert processed == 2


@pytest.mark.asyncio
async def test_backfill_bio_places_for_active_vaults_skips_deleted(
    async_session: AsyncSession
) -> None:
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
        await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**data, vault_id=target_vault.id)
        )

    counts = await bio_place_backfill_service.backfill_bio_places_for_active_vaults(async_session)

    assert counts == {active_vault.id: 1}

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    assert all(r.vault_id == active_vault.id for r in rows)
