"""Compatibility readers for the canonical dweller lifecycle and availability.

``lifecycle`` / ``availability`` are the authority. The legacy ``is_dead`` /
``is_permanently_dead`` / ``is_deleted`` / ``is_traded`` columns are compatibility
projections: these readers derive them from canonical state when a row is classified,
and fall back to the legacy column while a row is still NULL (pre-cutover). ``is_traded``
stays the existing sale-settlement marker and is intentionally not derived.

This lives in ``app/utils`` rather than ``app/services`` so CRUD may share it, mirroring
``app.utils.dweller_availability``.
"""

from datetime import datetime

from sqlmodel import and_, col, or_

from app.core.enums import AvailabilityEnum, ContentProvenanceEnum, LifecycleEnum
from app.models.dweller import Dweller

_DEAD_LIFECYCLES: frozenset[LifecycleEnum] = frozenset({LifecycleEnum.DEAD_REVIVABLE, LifecycleEnum.DEAD_PERMANENT})
_ARCHIVED_AVAILABILITIES: frozenset[AvailabilityEnum] = frozenset({AvailabilityEnum.ARCHIVE})
_PUBLIC_ONLY: tuple[AvailabilityEnum, ...] = (AvailabilityEnum.DEPARTURE, AvailabilityEnum.ARCHIVE)
_REUSABLE_PROVENANCES: tuple[ContentProvenanceEnum, ...] = (
    ContentProvenanceEnum.CURATED,
    ContentProvenanceEnum.GENERATED,
)


def is_dead(dweller: Dweller) -> bool:
    """Derived death projection: any dead lifecycle, else the legacy flag."""
    if dweller.lifecycle is not None:
        return dweller.lifecycle in _DEAD_LIFECYCLES
    return dweller.is_dead


def is_permanently_dead(dweller: Dweller) -> bool:
    """Derived permanent-death projection: ``dead_permanent`` only, else the legacy flag."""
    if dweller.lifecycle is not None:
        return dweller.lifecycle == LifecycleEnum.DEAD_PERMANENT
    return dweller.is_permanently_dead


def is_deleted(dweller: Dweller) -> bool:
    """Derived soft-delete projection: archived membership, else the legacy flag."""
    if dweller.availability is not None:
        return dweller.availability in _ARCHIVED_AVAILABILITIES
    return dweller.is_deleted


def is_traded(dweller: Dweller) -> bool:
    """The sale-settlement marker is its own authority, not a lifecycle projection."""
    return dweller.is_traded


def graveyard_conditions() -> tuple:
    """WHERE conditions for a memorial: canonical ``dead_permanent``, never a soft-delete flag.

    A reclassified legacy EXILE departure still carries ``is_permanently_dead``; keying on
    the canonical lifecycle excludes it. The NULL branch keeps genuine deaths written before
    the writers cut over visible.
    """
    return (
        or_(
            col(Dweller.lifecycle) == LifecycleEnum.DEAD_PERMANENT,
            and_(col(Dweller.lifecycle).is_(None), col(Dweller.is_permanently_dead)),
        ),
    )


def excluded_from_public_offers_conditions() -> tuple:
    """WHERE conditions excluding departures and retired archive content from public browsing.

    NULL availability (legacy rows) passes so the market keeps working before cutover.
    """
    return (
        or_(
            col(Dweller.availability).is_(None),
            ~col(Dweller.availability).in_(_PUBLIC_ONLY),
        ),
    )


def pool_eligible_conditions(now: datetime) -> tuple:
    """WHERE conditions for the shared recruitment pool.

    A person is claimable once they are a living departure, past the eligibility delay,
    and their content is safe to reuse: system/curated, or player-authored with explicit
    sharing consent. Unknown provenance stays private and is never listed.
    """
    return (
        col(Dweller.availability) == AvailabilityEnum.DEPARTURE,
        col(Dweller.departure_eligible_at) <= now,
        or_(
            col(Dweller.content_provenance).in_(_REUSABLE_PROVENANCES),
            col(Dweller.sharing_consent).is_(True),
        ),
    )
