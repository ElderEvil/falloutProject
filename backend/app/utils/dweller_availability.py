"""One availability policy for the assignments that draft vault dwellers.

Responders, explorers, and quest/team members all ask the same question: can this
dweller be sent out right now? The rules live here so the callers cannot drift.

Pure predicates stay session-free; ``available_dweller_conditions`` mirrors the
row-level filters for candidate queries, while the state-of-being filter stays in
Python because it lives in a JSONB attribute. This lives in ``app/utils`` rather
than ``app/services`` so CRUD may share it — the architecture guard lets CRUD
import only ``room_assignment_policy`` from the service layer (AGENTS.md rule 11).
"""

from enum import StrEnum

from sqlmodel import col

from app.core.enums import ADULT_AGE_GROUPS, DwellerStatusEnum
from app.models.dweller import Dweller
from app.options.races import can_take_purposeful_action
from app.utils.exceptions import ResourceConflictException


class DwellerAction(StrEnum):
    """Intentional actions whose age and state eligibility share one gate."""

    WORK = "work"
    TRAIN = "train"
    EXPLORE = "explore"
    FIGHT = "fight"
    SOCIAL = "social"


#: Actions that require a reasoning state. Feral ghouls and behemoths may only
#: fight and defend; work, training, exploration and social initiation are closed.
_REASONING_ACTIONS: frozenset[DwellerAction] = frozenset(
    {DwellerAction.WORK, DwellerAction.TRAIN, DwellerAction.EXPLORE, DwellerAction.SOCIAL}
)


def purposeful_action_error(dweller: Dweller, action: DwellerAction) -> str | None:
    """Age and state eligibility for one intentional action, or ``None`` when allowed."""
    if not getattr(dweller, "is_mature", True):
        return "dweller is not an adult"
    if action in _REASONING_ACTIONS and not can_take_purposeful_action(dweller):
        return "dweller cannot take purposeful actions"
    return None


#: Statuses that make a dweller unavailable for a new assignment.
UNAVAILABLE_STATUSES: frozenset[DwellerStatusEnum] = frozenset(
    {DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD}
)


def availability_error(
    dweller: Dweller,
    *,
    action: DwellerAction = DwellerAction.WORK,
    require_healthy: bool = False,
) -> str | None:
    """Why a dweller cannot perform an action, or ``None`` when they can.

    ``require_healthy`` adds the zero-health check the incident path needs; quest
    assignment historically omitted it, so callers opt in rather than silently
    tightening established behaviour.
    """
    if dweller.is_deleted:
        return "dweller is deleted"
    if dweller.is_dead:
        return "dweller is dead"
    if error := purposeful_action_error(dweller, action):
        return error
    if require_healthy and dweller.health <= 0:
        return "dweller is wounded"
    if dweller.status in UNAVAILABLE_STATUSES:
        return f"dweller is {dweller.status}"
    return None


def is_available(
    dweller: Dweller,
    *,
    action: DwellerAction = DwellerAction.WORK,
    require_healthy: bool = False,
) -> bool:
    """Whether a dweller passes the shared availability check."""
    return availability_error(dweller, action=action, require_healthy=require_healthy) is None


def is_incident_responder_available(dweller: Dweller) -> bool:
    """Healthy vault adults may respond unless already fighting in the Arena."""
    return (
        availability_error(dweller, action=DwellerAction.FIGHT, require_healthy=True) is None
        and dweller.status != DwellerStatusEnum.FIGHTING
    )


def available_dweller_conditions(*, require_healthy: bool = False) -> tuple:
    """Database conditions mirroring :func:`availability_error` for candidate queries."""
    conditions = [
        ~col(Dweller.is_deleted),
        col(Dweller.age_group).in_(ADULT_AGE_GROUPS),
        ~col(Dweller.is_dead),
        col(Dweller.status).notin_(list(UNAVAILABLE_STATUSES)),
    ]
    if require_healthy:
        conditions.append(col(Dweller.health) > 0)
    return tuple(conditions)


def require_vault_equipment_access(dweller: Dweller) -> None:
    """Storage equipment cannot be transferred to dwellers away from the vault."""
    if dweller.status in (DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING):
        raise ResourceConflictException(detail="Cannot change equipment while outside the vault.")
