"""Current tutorial selection and read-only credit for existing vault state."""

from collections.abc import Sequence
from datetime import UTC, timedelta
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import TrainingStatus
from app.crud import outfit as outfit_crud
from app.crud import weapon as weapon_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.exploration import exploration as exploration_crud
from app.crud.objective import objective_crud
from app.crud.quest import quest_crud
from app.crud.room import room as room_crud
from app.crud.training import training as training_crud
from app.models.objective import Objective, ObjectiveBase
from app.schemas.objective import ObjectiveCreate, ObjectiveRead
from app.services.room_assignment_policy import get_highest_special
from app.utils.objective_constants import normalize_room_type
from app.utils.time import utcnow


async def create_objective_for_vault(
    db_session: AsyncSession, vault_id: UUID, objective_data: ObjectiveCreate
) -> Objective:
    """Create a global objective template and link it to the vault; the service owns the commit."""
    objective = await objective_crud.create_for_vault(db_session, vault_id, objective_data, commit=False)
    await db_session.commit()
    return objective


async def get_objective_template(db_session: AsyncSession, objective_id: UUID) -> Objective:
    return await objective_crud.get(db_session, objective_id)


async def current_state_progress(db_session: AsyncSession, vault_id: UUID, objective: ObjectiveBase) -> int:
    """Credit existing state milestones without replaying events or writing on GET."""
    target = objective.target_entity or {}
    if objective.objective_type == "equip":
        item_crud = {"weapon": weapon_crud, "outfit": outfit_crud}.get(target.get("item_type"))
        return await item_crud.count_equipped(db_session, vault_id) if item_crud else 0
    if objective.objective_type == "reach":
        if target.get("reach_type", target.get("target")) in {"dweller_count", "population"}:
            return await dweller_crud.count_living_in_vault(db_session, vault_id)
        if target.get("reach_type", target.get("target")) == "level":
            return await dweller_crud.get_max_level(db_session, vault_id) or 0
    if objective.objective_type == "expedition" and not target.get("quest_type"):
        return len(await quest_crud.get_completed_quest_ids(db_session, vault_id))
    if objective.objective_type == "train" and not target.get("stat"):
        return len(await training_crud.get_by_vault(db_session, vault_id, status=TrainingStatus.COMPLETED))
    if objective.objective_type == "explore":
        # A departure target, not quest completion: credit any run already under way or finished.
        return await exploration_crud.count_by_vault(db_session, vault_id=vault_id)
    if objective.objective_type in {"build", "assign", "assign_correct"}:
        room_type = normalize_room_type(target.get("room_type"))
        rooms = await room_crud.get_all_by_vault(db_session, vault_id)
        matching = {
            room.id: room
            for room in rooms
            if not room_type or room_type in {"*", "any"} or normalize_room_type(room.name) == room_type
        }
        if objective.objective_type == "build":
            if target.get("additional"):
                # Construction only: floor area beyond the seeded quarter. A tier upgrade
                # raises capacity without changing size, so it must not complete this.
                baseline_size = target.get("baseline_size", 0)
                return 1 if sum(room.size or 0 for room in matching.values()) > baseline_size else 0
            return len(matching)
        dwellers = await dweller_crud.get_living_in_vault(db_session, vault_id)
        if objective.objective_type == "assign":
            return sum(dweller.room_id in matching for dweller in dwellers)
        return sum(
            1
            for dweller in dwellers
            if (room := matching.get(dweller.room_id)) is not None
            and room.ability is not None
            and get_highest_special(dweller) == room.ability
        )
    return 0


def _reach_type(objective: ObjectiveBase) -> str | None:
    """The reach kind an objective measures, normalised, or None for other types."""
    if objective.objective_type != "reach":
        return None
    target = objective.target_entity or {}
    reach_type = target.get("reach_type", target.get("target"))
    if not isinstance(reach_type, str):
        return None
    return "dweller_count" if reach_type == "population" else reach_type


async def reach_progress_by_objective(
    db_session: AsyncSession, vault_id: UUID, objectives: Sequence[ObjectiveRead]
) -> dict[UUID, int]:
    """Derive reach progress for a whole page with at most one query per reach kind.

    Reach objectives record progress from membership events, so a vault that reached
    the milestone before the objective was assigned would otherwise read 0 — while the
    claim path credits the same state. Both paths must agree, not just the current step.
    """
    kinds = {kind for objective in objectives if (kind := _reach_type(objective)) is not None}
    if not kinds:
        return {}

    current: dict[str, int] = {}
    if "dweller_count" in kinds:
        current["dweller_count"] = await dweller_crud.count_living_in_vault(db_session, vault_id)
    if "level" in kinds:
        current["level"] = await dweller_crud.get_max_level(db_session, vault_id) or 0

    return {objective.id: current[kind] for objective in objectives if (kind := _reach_type(objective)) in current}


async def read_objectives(
    db_session: AsyncSession, vault_id: UUID, *, skip: int = 0, limit: int = 100
) -> Sequence[ObjectiveRead]:
    """Read progress, deriving already-met state for the guided step and every reach objective."""
    objectives = await objective_crud.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)
    reach_progress = await reach_progress_by_objective(db_session, vault_id, objectives)
    for objective in objectives:
        if objective.id in reach_progress:
            objective.progress = min(objective.total, max(objective.progress, reach_progress[objective.id]))
    current_id = await objective_crud.get_current_starter_id(db_session, vault_id)
    current = next((objective for objective in objectives if objective.id == current_id), None)
    if current is not None:
        current.progress = min(
            current.total, max(current.progress, await current_state_progress(db_session, vault_id, current))
        )
    from app.services.progression.objectives.refresh_service import objective_periods

    daily, weekly = objective_periods(utcnow())
    achievements = await objective_crud.get_assignable_achievements(db_session)
    for objective in objectives:
        if objective.category == "daily":
            objective.resets_at = (daily + timedelta(days=1)).replace(tzinfo=UTC)
        elif objective.category == "weekly":
            objective.resets_at = (weekly + timedelta(days=7)).replace(tzinfo=UTC)
        if objective.track_key:
            objective.next_stage_challenge = next(
                (
                    stage.challenge
                    for stage in achievements
                    if stage.track_key == objective.track_key and (stage.sequence or 0) > (objective.sequence or 0)
                ),
                None,
            )
    return objectives
