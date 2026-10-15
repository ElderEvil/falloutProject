"""Shared recruitment pool: listing and atomic identity-preserving claims."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    AvailabilityEnum,
    ContentProvenanceEnum,
    GenderEnum,
    LifecycleEnum,
    RarityEnum,
)
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.departure_pool_service import departure_pool_service
from app.services.trading_post_service import trade_value
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException


def _dweller_data(**overrides: object) -> dict:
    data: dict = {
        "first_name": "Nomad",
        "last_name": "Wanderer",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "birth_date": datetime.utcnow() - timedelta(days=365 * 30),
        "level": 7,
        "experience": 420,
        "max_health": 120,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        **dict.fromkeys(SPECIAL_STATS, 4),
    }
    data.update(overrides)
    return data


async def _create(db_session: AsyncSession, vault: Vault, **overrides: object) -> Dweller:
    return await crud.dweller.create(
        db_session=db_session, obj_in=DwellerCreate(**_dweller_data(**overrides), vault_id=vault.id)
    )


async def _depart(
    db_session: AsyncSession,
    dweller: Dweller,
    *,
    source_vault_id,
    provenance: ContentProvenanceEnum | None = ContentProvenanceEnum.GENERATED,
    consent: bool | None = None,
    eligible: bool = True,
) -> Dweller:
    """Turn a living dweller into a pool departure (or an ineligible/private one)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    dweller.lifecycle = LifecycleEnum.WASTELAND
    dweller.availability = AvailabilityEnum.DEPARTURE
    dweller.vault_id = None
    dweller.previous_vault_id = source_vault_id
    dweller.content_provenance = provenance
    dweller.sharing_consent = consent
    dweller.departed_at = now - timedelta(days=8)
    dweller.departure_eligible_at = now - timedelta(days=1) if eligible else now + timedelta(days=1)
    db_session.add(dweller)
    await db_session.commit()
    await db_session.refresh(dweller)
    return dweller


@pytest.mark.asyncio
async def test_list_pool_excludes_own_departures_and_ineligible(async_session: AsyncSession, vault: Vault) -> None:
    source_id = uuid4()
    claimable = await _depart(async_session, await _create(async_session, vault), source_vault_id=source_id)
    await _depart(async_session, await _create(async_session, vault), source_vault_id=uuid4(), eligible=False)
    await _depart(
        async_session,
        await _create(async_session, vault),
        source_vault_id=uuid4(),
        provenance=ContentProvenanceEnum.PLAYER_EDITED,
        consent=None,
    )
    await _depart(async_session, await _create(async_session, vault), source_vault_id=vault.id)

    pool = await departure_pool_service.list_pool(async_session, vault)

    assert [d.id for d in pool] == [claimable.id]


@pytest.mark.asyncio
async def test_claim_transfers_ownership_and_preserves_identity(async_session: AsyncSession, vault: Vault) -> None:
    await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
    dweller = await _depart(
        async_session, await _create(async_session, vault, level=7, experience=420), source_vault_id=uuid4()
    )

    claimed = await departure_pool_service.claim(async_session, vault, dweller.id)

    assert claimed.id == dweller.id
    assert claimed.level == 7
    assert claimed.experience == 420
    assert claimed.lifecycle is LifecycleEnum.ALIVE
    assert claimed.availability is AvailabilityEnum.VAULT
    assert claimed.vault_id == vault.id
    assert claimed.previous_vault_id is None
    assert claimed.departed_at is None
    assert claimed.departure_eligible_at is None
    await async_session.refresh(vault)
    assert vault.bottle_caps == 100_000 - trade_value(dweller)


@pytest.mark.asyncio
async def test_claim_rejects_a_vault_at_population_capacity(async_session: AsyncSession, vault: Vault) -> None:
    """A buyer at its population cap is refused before any caps are charged."""
    await crud.vault.update(
        db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000, "population_max": 1}
    )
    dweller = await _depart(async_session, await _create(async_session, vault), source_vault_id=uuid4())
    await _create(async_session, vault, first_name="Filler", last_name="Dweller")

    with pytest.raises(ResourceConflictException, match="population capacity"):
        await departure_pool_service.claim(async_session, vault, dweller.id)

    await async_session.refresh(vault)
    assert vault.bottle_caps == 100_000


@pytest.mark.asyncio
async def test_claim_rejects_a_duplicate_active_identity(async_session: AsyncSession, vault: Vault) -> None:
    """A curated name that is already active in the buyer vault is refused, like templates."""
    await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
    dweller = await _depart(
        async_session,
        await _create(async_session, vault, first_name="Sarah", last_name="Lyons"),
        source_vault_id=uuid4(),
    )
    await _create(async_session, vault, first_name="Sarah", last_name="Lyons")

    with pytest.raises(ResourceConflictException, match="already has an active"):
        await departure_pool_service.claim(async_session, vault, dweller.id)

    await async_session.refresh(vault)
    assert vault.bottle_caps == 100_000


@pytest.mark.asyncio
async def test_claim_rejects_your_own_departure(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _depart(async_session, await _create(async_session, vault), source_vault_id=vault.id)

    with pytest.raises(VaultOperationException, match="your own departure"):
        await departure_pool_service.claim(async_session, vault, dweller.id)


@pytest.mark.asyncio
async def test_claim_rejects_a_not_yet_eligible_departure(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _depart(async_session, await _create(async_session, vault), source_vault_id=uuid4(), eligible=False)

    with pytest.raises(ResourceConflictException, match="not yet eligible"):
        await departure_pool_service.claim(async_session, vault, dweller.id)


@pytest.mark.asyncio
async def test_claim_rejects_unshared_player_content(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _depart(
        async_session,
        await _create(async_session, vault),
        source_vault_id=uuid4(),
        provenance=ContentProvenanceEnum.PLAYER_EDITED,
        consent=None,
    )

    with pytest.raises(ResourceConflictException, match="not shared"):
        await departure_pool_service.claim(async_session, vault, dweller.id)


@pytest.mark.asyncio
async def test_claim_rejects_a_person_already_taken(async_session: AsyncSession, vault: Vault) -> None:
    await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
    dweller = await _depart(async_session, await _create(async_session, vault), source_vault_id=uuid4())

    await departure_pool_service.claim(async_session, vault, dweller.id)

    with pytest.raises(ResourceConflictException, match="no longer available"):
        await departure_pool_service.claim(async_session, vault, dweller.id)


@pytest.mark.asyncio
async def test_claim_rejects_an_unknown_dweller(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(ResourceNotFoundException):
        await departure_pool_service.claim(async_session, vault, uuid4())
