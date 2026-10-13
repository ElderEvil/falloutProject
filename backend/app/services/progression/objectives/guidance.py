"""Current tutorial selection and read-only credit for existing vault state."""

from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.dweller import dweller as dweller_crud
from app.crud.objective import objective_crud
from app.crud.quest import quest_crud
from app.crud.room import room as room_crud
from app.crud.training import training as training_crud
from app.models.objective import ObjectiveBase
from app.models.training import TrainingStatus
from app.schemas.objective import ObjectiveRead
from app.utils.objective_constants import normalize_room_type


async def current_state_progress(db_session: AsyncSession, vault_id: UUID4, objective: ObjectiveBase) -> int:
    """Credit existing state milestones without replaying events or writing on GET."""
    target = objective.target_entity or {}
    if objective.objective_type == "reach":
        if target.get("reach_type", target.get("target")) in {"dweller_count", "population"}:
            return await dweller_crud.count_living_in_vault(db_session, vault_id)
        if target.get("reach_type", target.get("target")) == "level":
            return await dweller_crud.get_max_level(db_session, vault_id) or 0
    if objective.objective_type == "expedition" and not target.get("quest_type"):
        return len(await quest_crud.get_completed_quest_ids(db_session, vault_id))
    if objective.objective_type == "train" and not target.get("stat"):
        return len(await training_crud.get_by_vault(db_session, vault_id, status=TrainingStatus.COMPLETED))
    if objective.objective_type in {"build", "assign"}:
        room_type = normalize_room_type(target.get("room_type"))
        rooms = await room_crud.get_all_by_vault(db_session, vault_id)
        matching = {
            room.id
            for room in rooms
            if not room_type or room_type in {"*", "any"} or normalize_room_type(room.name) == room_type
        }
        if objective.objective_type == "build":
            return len(matching)
        return sum(
            dweller.room_id in matching for dweller in await dweller_crud.get_living_in_vault(db_session, vault_id)
        )
    return 0


async def read_objectives(
    db_session: AsyncSession, vault_id: UUID4, *, skip: int = 0, limit: int = 100
) -> Sequence[ObjectiveRead]:
    """Read progress, deriving already-met state only for the current guided step."""
    objectives = await objective_crud.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)
    current_id = await objective_crud.get_current_starter_id(db_session, vault_id)
    current = next((objective for objective in objectives if objective.id == current_id), None)
    if current is not None:
        current.progress = min(
            current.total, max(current.progress, await current_state_progress(db_session, vault_id, current))
        )
    return objectives
