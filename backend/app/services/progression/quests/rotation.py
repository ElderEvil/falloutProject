"""Daily and weekly quest rotation on the objectives UTC period clock.

This service is the transaction owner: it locks the vault row, stages every link
and game-state write through helpers that never commit, and commits once at the end.
"""

import random
from datetime import datetime
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import QuestType
from app.crud.dweller import dweller as dweller_crud
from app.crud.game_state import game_state_crud
from app.crud.quest import quest_crud
from app.crud.vault import vault as vault_crud
from app.models.vault_quest import VaultQuestCompletionLink
from app.services.progression.objectives.refresh_service import objective_periods
from app.services.progression.quests.availability import REVEAL_MARGIN, highest_mandatory_level_requirement
from app.utils.time import utcnow

DAILY_COUNT = 3
WEEKLY_COUNT = 1


def _is_in_flight(link: VaultQuestCompletionLink) -> bool:
    """A party away from the vault, or one with unclaimed prizes, keeps its link state.

    A claimed quest also keeps its historical ``started_at``, so ``is_completed`` must be
    excluded or a completed daily would never be re-offered.
    """
    return not link.is_completed and (
        link.started_at is not None or link.return_started_at is not None or link.is_reward_ready
    )


def _reset_link(link: VaultQuestCompletionLink, *, is_visible: bool) -> None:
    """Re-offer a quest in place; links are never deleted because reads would resurrect them."""
    link.is_completed = False
    link.is_reward_ready = False
    link.completed_at = None
    link.granted_rewards = None
    link.started_at = None
    link.return_started_at = None
    link.return_completes_at = None
    link.duration_minutes = None
    link.is_visible = is_visible


async def _roll_pool(
    db: AsyncSession, vault_id: UUID, quest_type: QuestType, count: int, reveal_threshold: int
) -> tuple[int, bool]:
    """Offer ``count`` quests of one pool and hide the rest, returning the offered count and pool presence.

    Unsettled links (a party away, or prizes unclaimed) are excluded from the draw
    before sampling, so a carried-over quest never consumes one of the fresh slots;
    they keep their state and stay visible. Only quests inside the vault's reveal
    window are sampled: a mandatory LEVEL gate above ``reveal_threshold`` is dropped
    from both read paths, so offering it would silently consume a slot the vault can
    never see.
    """
    quests = await quest_crud.get_rotation_candidates(db, quest_type)
    if not quests:
        return 0, False
    quest_ids = [quest.id for quest in quests]
    links = {link.quest_id: link for link in await quest_crud.get_links_for_quest_ids(db, vault_id, quest_ids)}
    in_flight = {quest_id for quest_id, link in links.items() if _is_in_flight(link)}
    fresh = [quest for quest in quests if quest.id not in in_flight]
    eligible = [quest for quest in fresh if highest_mandatory_level_requirement(quest) <= reveal_threshold]
    offered = {quest.id for quest in random.sample(eligible, min(count, len(eligible)))}
    await quest_crud.insert_links_if_absent(db, vault_id, {quest.id: quest.id in offered for quest in fresh})
    for quest_id, link in links.items():
        if quest_id in in_flight:
            link.is_visible = True
        else:
            _reset_link(link, is_visible=quest_id in offered)
    return len(offered), True


async def ensure_current_quest_rotation(db: AsyncSession, vault_id: UUID, *, now: datetime | None = None) -> int:
    """Rotate expired daily/weekly quest pools and commit atomically; returns quests re-offered.

    Idempotent within a period: an already-current vault commits (releasing the vault
    lock) and reports 0. A populated pool records its period even with zero offers, so
    a mid-period trigger cannot re-roll; an empty catalog defers until it is seeded.
    """
    await vault_crud.lock_for_update(db, vault_id)
    state = await game_state_crud.get_or_create(db, vault_id, commit=False)
    await db.refresh(state)
    daily, weekly = objective_periods(now or utcnow())
    daily_current = state.daily_quests_period is not None and state.daily_quests_period >= daily
    weekly_current = state.weekly_quests_period is not None and state.weekly_quests_period >= weekly
    if daily_current and weekly_current:
        await db.commit()  # Release the vault lock even when a sweep has no work.
        return 0

    reveal_threshold = (await dweller_crud.get_max_level(db, vault_id) or 0) + REVEAL_MARGIN
    offered = 0
    for quest_type, count, period, field in (
        (QuestType.DAILY, DAILY_COUNT, daily, "daily_quests_period"),
        (QuestType.REPEATABLE, WEEKLY_COUNT, weekly, "weekly_quests_period"),
    ):
        previous = getattr(state, field)
        if previous is not None and previous >= period:
            continue  # Monotonic guard: never re-roll on a clock rollback.
        rolled, populated = await _roll_pool(db, vault_id, quest_type, count, reveal_threshold)
        if not populated:
            continue
        offered += rolled
        setattr(state, field, period)

    db.add(state)
    await db.commit()
    return offered
