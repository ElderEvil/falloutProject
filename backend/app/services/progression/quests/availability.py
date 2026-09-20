"""Quest availability: office gate, chain reveal, and the vault quest read assembly.

The read-path gate that the start path also consumes (via ``quest_service``) so they
can never disagree. Quest lifecycle — start, claim, complete — lives in ``service.py``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from pydantic import UUID4
from sqlalchemy import inspect
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.quest import Quest
from app.models.quest_requirement import RequirementType
from app.schemas.quest import QuestRead
from app.services.progression.quests.requirements import vault_missing_requirements

OFFICE_ROOM_TYPE = "overseers_office"
OFFICE_LOCK_REASON = "Requires Overseer's Office"
CHAIN_LOCK_REASON = "Requires completing a previous quest"
# Availability filtering happens before pagination, so the full vault quest set is fetched first.
_AVAILABLE_QUESTS_FETCH_LIMIT = 10_000
# A quest whose highest mandatory LEVEL gate is more than this many levels above the
# vault's max dweller level is hidden entirely (progressive reveal, like the real game).
REVEAL_MARGIN = 10


@dataclass
class QuestAvailability:
    """Whether a vault can start a quest, and why not when it cannot."""

    available: bool
    missing: list[str] = field(default_factory=list)
    lock_reason: str | None = None


def _highest_mandatory_level_requirement(quest_read: QuestRead) -> int:
    """Highest mandatory LEVEL requirement of a quest read, or 0 when none."""
    highest = 0
    for req in quest_read.quest_requirements or []:
        if req.requirement_type == RequirementType.LEVEL and req.is_mandatory:
            level = req.requirement_data.get("level")
            if isinstance(level, int):
                highest = max(highest, level)
    return highest


async def _chain_lock_reason(
    db_session: AsyncSession,
    previous_quest_id: UUID4,
    resolve_quest: Callable[[UUID4], Quest | None] | None,
) -> str:
    """Requirement-driven unlock feedback: name the predecessor, else the generic reason.

    ``resolve_quest`` avoids per-quest lookups on the batch read path (the caller
    already holds the vault quest map); a lone caller (the start path) falls back
    to one query only when no resolver is supplied.
    """
    predecessor = resolve_quest(previous_quest_id) if resolve_quest is not None else None
    if predecessor is None and resolve_quest is None:
        predecessor = await crud.quest_crud.get_or_none(db_session, previous_quest_id)
    if predecessor is not None:
        return f"Complete '{predecessor.title}' first"
    return CHAIN_LOCK_REASON


async def quest_availability(
    db_session: AsyncSession,
    vault_id: UUID4,
    quest: Quest,
    *,
    has_office: bool | None = None,
    completed_quest_ids: set[UUID4] | None = None,
    resolve_quest: Callable[[UUID4], Quest | None] | None = None,
) -> QuestAvailability:
    """Whether a vault can start a quest: Office rule, chain predecessor, then mandatory requirements.

    This is the single source of truth for quest availability; both the vault quest
    read and the start path consume it so they can never disagree. The vault-level
    lookups can be passed in so a batch caller resolves them once instead of per quest.
    """
    if has_office is None:
        has_office = await crud.room.has_room_type(db_session, vault_id, OFFICE_ROOM_TYPE)
    if not has_office:
        return QuestAvailability(available=False, lock_reason=OFFICE_LOCK_REASON)

    if completed_quest_ids is None:
        completed_quest_ids = await crud.quest_crud.get_completed_quest_ids(db_session, vault_id)
    if quest.previous_quest_id is not None and quest.previous_quest_id not in completed_quest_ids:
        lock_reason = await _chain_lock_reason(db_session, quest.previous_quest_id, resolve_quest)
        return QuestAvailability(available=False, lock_reason=lock_reason)

    state = inspect(quest)
    if state is not None and "quest_requirements" in state.unloaded:
        await db_session.refresh(quest, ["quest_requirements"])
    missing = await vault_missing_requirements(db_session, vault_id, quest)
    if missing:
        return QuestAvailability(available=False, missing=missing, lock_reason="; ".join(missing))

    return QuestAvailability(available=True)


async def get_quests_for_vault(
    db_session: AsyncSession,
    vault_id: UUID4,
    skip: int = 0,
    limit: int = 100,
    available_only: bool = False,
) -> Sequence[QuestRead]:
    """Vault quest read: link state from CRUD plus honest availability from the shared function.

    The full vault quest set is fetched, reveal/availability filtering applied, then
    ``skip``/``limit`` paginate the filtered result so later visible quests fill a page.
    """
    quest_reads = await crud.quest_crud.get_multi_for_vault(
        db_session=db_session, vault_id=vault_id, skip=0, limit=_AVAILABLE_QUESTS_FETCH_LIMIT
    )
    quests = await crud.quest_crud.get_multi_by_ids(db_session, [quest_read.id for quest_read in quest_reads])
    quest_by_id = {quest.id: quest for quest in quests}
    has_office = await crud.room.has_room_type(db_session, vault_id, OFFICE_ROOM_TYPE)
    completed_quest_ids = await crud.quest_crud.get_completed_quest_ids(db_session, vault_id)
    max_dweller_level = await crud.dweller.get_max_level(db_session, vault_id) or 0
    reveal_threshold = max_dweller_level + REVEAL_MARGIN

    available_reads = []
    visible_reads = []
    for quest_read in quest_reads:
        quest = quest_by_id.get(quest_read.id)
        if quest is None:
            continue
        if has_office and _highest_mandatory_level_requirement(quest_read) > reveal_threshold:
            continue
        availability = await quest_availability(
            db_session,
            vault_id,
            quest,
            has_office=has_office,
            completed_quest_ids=completed_quest_ids,
            resolve_quest=quest_by_id.get,
        )
        quest_read.is_visible = quest_read.is_visible and availability.available
        quest_read.is_locked = not availability.available
        quest_read.lock_reason = availability.lock_reason
        visible_reads.append(quest_read)
        if available_only and availability.available:
            available_reads.append(quest_read)

    if available_only:
        return available_reads[skip : skip + limit]

    return visible_reads[skip : skip + limit]
