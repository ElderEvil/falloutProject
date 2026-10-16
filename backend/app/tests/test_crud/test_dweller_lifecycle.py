"""Regression coverage for the canonical dweller lifecycle and the graveyard reader.

Slice 1 of #831: a legacy EXILE tombstone was written as a permanent death, so a dweller
who merely left surfaced in the graveyard. Canonical ``lifecycle``/``availability`` now
decide, and the compatibility readers in ``app/utils/dweller_lifecycle.py`` keep the legacy
booleans as derived projections. These tests run the real session and assert on the rows
the queries return, not on a stubbed CRUD return value.
"""

from datetime import datetime, timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AvailabilityEnum,
    DeathCauseEnum,
    DwellerStatusEnum,
    LifecycleEnum,
)
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.family.death_service import death_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils import dweller_lifecycle


async def _dweller(async_session: AsyncSession, vault: Vault, **overrides: object) -> Dweller:
    data = create_fake_dweller()
    data.update({"status": DwellerStatusEnum.IDLE.value, "health": 100, "max_health": 100})
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))
    for key, value in overrides.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def test_graveyard_excludes_a_departed_row_still_carrying_death_flags(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A reclassified EXILE departure keeps its legacy flags but is not a memorial."""
    departed = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.WASTELAND,
        availability=AvailabilityEnum.DEPARTURE,
        is_dead=True,
        is_permanently_dead=True,
        death_cause=DeathCauseEnum.EXILE,
        death_timestamp=datetime(2026, 1, 1),
    )

    assert [row.id for row in await crud.dweller.get_graveyard(async_session, vault.id)] == []
    assert dweller_lifecycle.is_permanently_dead(departed) is False


async def test_graveyard_includes_a_canonical_permanent_death(async_session: AsyncSession, vault: Vault) -> None:
    """Canonical ``dead_permanent`` wins even when the legacy flag disagrees."""
    memorial = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.DEAD_PERMANENT,
        availability=AvailabilityEnum.ARCHIVE,
        is_permanently_dead=False,
    )

    rows = await crud.dweller.get_graveyard(async_session, vault.id)
    assert [row.id for row in rows] == [memorial.id]


async def test_graveyard_includes_an_unclassified_legacy_permanent_death(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A death written before the writers cut over stays visible through the fallback."""
    memorial = await _dweller(
        async_session,
        vault,
        is_dead=True,
        is_permanently_dead=True,
        death_cause=DeathCauseEnum.COMBAT,
        death_timestamp=datetime(2026, 1, 1),
    )

    rows = await crud.dweller.get_graveyard(async_session, vault.id)
    assert [row.id for row in rows] == [memorial.id]


async def test_compatibility_readers_derive_from_canonical_state(async_session: AsyncSession, vault: Vault) -> None:
    """The legacy booleans are projections over lifecycle/availability, not authorities."""
    departed = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.WASTELAND,
        availability=AvailabilityEnum.DEPARTURE,
        is_dead=True,
        is_permanently_dead=True,
    )
    archived = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.ALIVE,
        availability=AvailabilityEnum.ARCHIVE,
        is_deleted=False,
    )

    assert dweller_lifecycle.is_dead(departed) is False
    assert dweller_lifecycle.is_permanently_dead(departed) is False
    assert dweller_lifecycle.is_deleted(departed) is False
    assert dweller_lifecycle.is_deleted(archived) is True


async def test_public_market_listing_excludes_departures(async_session: AsyncSession, vault: Vault) -> None:
    """A departure is not a public market listing even while soft-deleted."""
    departed = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.WASTELAND,
        availability=AvailabilityEnum.DEPARTURE,
        is_deleted=True,
    )
    listing = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.ALIVE,
        availability=AvailabilityEnum.MARKET,
        is_deleted=True,
    )

    ids = {row.id for row in await crud.dweller.get_tradable(async_session, vault_id=vault.id)}
    assert listing.id in ids
    assert departed.id not in ids


async def test_classified_resident_permanent_death_lands_in_the_graveyard(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A migrated ALIVE/VAULT resident's death must move canonical state or the graveyard loses them.

    The migration classifies living residents as ``alive``/``vault``; a death writer that only
    flips the legacy flags leaves ``lifecycle`` alive, so ``get_graveyard`` (which prefers the
    canonical state) stops seeing genuine deaths.
    """
    resident = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.ALIVE,
        availability=AvailabilityEnum.VAULT,
    )

    await death_service.mark_as_dead(async_session, resident, DeathCauseEnum.HEALTH, permanent=True)
    await async_session.refresh(resident)

    assert resident.lifecycle is LifecycleEnum.DEAD_PERMANENT
    assert resident.availability is AvailabilityEnum.ARCHIVE
    assert [row.id for row in await crud.dweller.get_graveyard(async_session, vault.id)] == [resident.id]


async def test_classified_resident_temporary_death_stays_revivable(async_session: AsyncSession, vault: Vault) -> None:
    """A non-permanent death of a classified resident is revivable and not a memorial."""
    resident = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.ALIVE,
        availability=AvailabilityEnum.VAULT,
    )

    await death_service.mark_as_dead(async_session, resident, DeathCauseEnum.HEALTH)
    await async_session.refresh(resident)

    assert resident.lifecycle is LifecycleEnum.DEAD_REVIVABLE
    assert resident.availability is AvailabilityEnum.VAULT
    assert await crud.dweller.get_graveyard(async_session, vault.id) == []


async def test_permanent_death_expiry_updates_canonical_state_and_graveyard(
    async_session: AsyncSession, vault: Vault
) -> None:
    """The expiry sweep promotes a revivable death to canonical ``dead_permanent``/``archive``."""
    expired = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.DEAD_REVIVABLE,
        availability=AvailabilityEnum.VAULT,
        is_dead=True,
        is_permanently_dead=False,
        death_cause=DeathCauseEnum.EXPLORATION,
        death_timestamp=datetime.utcnow() - timedelta(days=10),
    )

    count = await death_service.check_and_mark_permanent_deaths(async_session)
    await async_session.refresh(expired)

    assert count == 1
    assert expired.lifecycle is LifecycleEnum.DEAD_PERMANENT
    assert expired.availability is AvailabilityEnum.ARCHIVE
    assert [row.id for row in await crud.dweller.get_graveyard(async_session, vault.id)] == [expired.id]


async def test_revival_restores_canonical_lifecycle(async_session: AsyncSession, vault: Vault) -> None:
    """Reviving a classified dead resident returns them to canonical ``alive``/``vault``."""
    dead = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.DEAD_REVIVABLE,
        availability=AvailabilityEnum.VAULT,
        is_dead=True,
        is_permanently_dead=False,
        death_cause=DeathCauseEnum.HEALTH,
        death_timestamp=datetime.utcnow() - timedelta(days=1),
        health=0,
    )
    vault.bottle_caps = 10_000
    async_session.add(vault)
    await async_session.commit()
    owner = await crud.user.get(async_session, vault.user_id)

    await death_service.revive_dweller(async_session, dead.id, owner)
    await async_session.refresh(dead)

    assert dead.lifecycle is LifecycleEnum.ALIVE
    assert dead.availability is AvailabilityEnum.VAULT
    assert await crud.dweller.get_graveyard(async_session, vault.id) == []


async def test_memorial_is_excluded_from_recycling_and_purge(async_session: AsyncSession, vault: Vault) -> None:
    """A permanent death is an immutable memorial: never recycled or hard-deleted."""
    memorial = await _dweller(
        async_session,
        vault,
        lifecycle=LifecycleEnum.DEAD_PERMANENT,
        availability=AvailabilityEnum.ARCHIVE,
        is_permanently_dead=True,
        is_deleted=True,
        deleted_at=datetime.utcnow(),
    )

    recyclable = await crud.dweller.get_recyclable(async_session, limit=10)
    purgeable = await crud.dweller.get_soft_deleted_before(async_session, datetime.utcnow(), limit=10)

    assert memorial.id not in {row.id for row in recyclable}
    assert memorial.id not in {row.id for row in purgeable}
