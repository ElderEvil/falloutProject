"""Regression coverage for the canonical dweller lifecycle and the graveyard reader.

Slice 1 of #831: a legacy EXILE tombstone was written as a permanent death, so a dweller
who merely left surfaced in the graveyard. Canonical ``lifecycle``/``availability`` now
decide, and the compatibility readers in ``app/utils/dweller_lifecycle.py`` keep the legacy
booleans as derived projections. These tests run the real session and assert on the rows
the queries return, not on a stubbed CRUD return value.
"""

from datetime import datetime

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
