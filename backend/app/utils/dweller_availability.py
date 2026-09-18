"""One availability policy for the assignments that draft vault dwellers.

Responders, explorers, and quest/team members all ask the same question: can this
dweller be sent out right now? The rules live here so the callers cannot drift.

Pure predicates stay session-free; ``available_dweller_conditions`` mirrors them
for candidate queries. This lives in ``app/utils`` rather than ``app/services``
so CRUD may share it — the architecture guard lets CRUD import only
``room_assignment_policy`` from the service layer (AGENTS.md rule 11).
"""

from sqlmodel import col

from app.core.enums import ADULT_AGE_GROUPS, DwellerStatusEnum
from app.models.dweller import Dweller

#: Statuses that make a dweller unavailable for a new assignment.
UNAVAILABLE_STATUSES: frozenset[DwellerStatusEnum] = frozenset(
    {DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD}
)


def availability_error(dweller: Dweller, *, require_healthy: bool = False) -> str | None:
    """Why a dweller cannot be assigned, or ``None`` when they can.

    ``require_healthy`` adds the zero-health check the incident path needs; quest
    assignment historically omitted it, so callers opt in rather than silently
    tightening established behaviour.
    """
    if dweller.is_deleted:
        return "dweller is deleted"
    if not dweller.is_mature:
        return "dweller is not an adult"
    if dweller.is_dead:
        return "dweller is dead"
    if require_healthy and dweller.health <= 0:
        return "dweller is wounded"
    if dweller.status in UNAVAILABLE_STATUSES:
        return f"dweller is {dweller.status}"
    return None


def is_available(dweller: Dweller, *, require_healthy: bool = False) -> bool:
    """Whether a dweller passes the shared availability check."""
    return availability_error(dweller, require_healthy=require_healthy) is None


def available_dweller_conditions(*, require_healthy: bool = False) -> tuple:
    """Database conditions mirroring :func:`availability_error` for candidate queries."""
    conditions = [
        ~col(Dweller.is_deleted),
        col(Dweller.is_adult),
        col(Dweller.age_group).in_(ADULT_AGE_GROUPS),
        ~col(Dweller.is_dead),
        col(Dweller.status).notin_(list(UNAVAILABLE_STATUSES)),
    ]
    if require_healthy:
        conditions.append(col(Dweller.health) > 0)
    return tuple(conditions)
