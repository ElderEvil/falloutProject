import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from pydantic import UUID4
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.crud.vault_mixin import VaultActionsMixin
from app.models import Vault
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate, QuestRead, QuestRequirementRead, QuestRewardRead, QuestUpdate
from app.services.notification_service import notification_service
from app.services.reward_service import reward_service
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


async def _batch_load_quest_details(
    db_session: AsyncSession,
    quest_ids: list[UUID4],
) -> tuple[dict[UUID4, list[QuestRequirement]], dict[UUID4, list[QuestReward]]]:
    """Batch load requirements and rewards for multiple quests in 2 queries."""
    reqs_by_quest: dict[UUID4, list[QuestRequirement]] = defaultdict(list)
    if quest_ids:
        req_stmt = select(QuestRequirement).where(QuestRequirement.quest_id.in_(quest_ids))
        req_result = await db_session.execute(req_stmt)
        for req in req_result.scalars().all():
            reqs_by_quest[req.quest_id].append(req)

    rewards_by_quest: dict[UUID4, list[QuestReward]] = defaultdict(list)
    if quest_ids:
        rew_stmt = select(QuestReward).where(QuestReward.quest_id.in_(quest_ids))
        rew_result = await db_session.execute(rew_stmt)
        for rew in rew_result.scalars().all():
            rewards_by_quest[rew.quest_id].append(rew)

    return reqs_by_quest, rewards_by_quest


class CRUDQuest(
    CRUDBase[Quest, QuestCreate, QuestUpdate], VaultActionsMixin[Vault], CompletionMixin[VaultQuestCompletionLink]
):
    def __init__(self, model: type[Quest], link_model: type[VaultQuestCompletionLink]):
        super().__init__(model)
        self.link_model = link_model

    async def get_multi(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> Sequence[QuestRead]:
        """Get all quests without vault-specific data."""
        query = select(Quest).offset(skip).limit(limit).order_by(Quest.id)
        response = await db_session.execute(query)
        quests = response.scalars().all()

        _ = include_deleted

        quest_ids = [q.id for q in quests]
        reqs_by_quest, rewards_by_quest = await _batch_load_quest_details(db_session, quest_ids)

        result_items = []
        for quest in quests:
            reqs = reqs_by_quest.get(quest.id, [])
            rewards = rewards_by_quest.get(quest.id, [])

            result_items.append(
                QuestRead(
                    id=quest.id,
                    title=quest.title,
                    short_description=quest.short_description,
                    long_description=quest.long_description,
                    requirements=quest.requirements,
                    rewards=quest.rewards,
                    quest_type=quest.quest_type,
                    quest_category=quest.quest_category,
                    chain_id=quest.chain_id,
                    chain_order=quest.chain_order,
                    duration_minutes=quest.duration_minutes,
                    previous_quest_id=quest.previous_quest_id,
                    next_quest_id=quest.next_quest_id,
                    created_at=quest.created_at,
                    updated_at=quest.updated_at,
                    is_visible=True,
                    is_completed=False,
                    started_at=None,
                    quest_requirements=[
                        QuestRequirementRead(
                            id=req.id,
                            requirement_type=req.requirement_type,
                            requirement_data=req.requirement_data,
                            is_mandatory=req.is_mandatory,
                        )
                        for req in reqs
                    ]
                    if reqs
                    else None,
                    quest_rewards=[
                        QuestRewardRead(
                            id=rew.id,
                            reward_type=rew.reward_type,
                            reward_data=rew.reward_data,
                            reward_chance=rew.reward_chance,
                            item_data=rew.item_data,
                        )
                        for rew in rewards
                    ]
                    if rewards
                    else None,
                )
            )

        return result_items

    async def get_multi_for_vault(
        self, *, db_session: AsyncSession, skip: int, limit: int, vault_id: UUID4
    ) -> Sequence[QuestRead]:
        existing_link_query = select(self.link_model.quest_id).where(self.link_model.vault_id == vault_id)

        missing_quests_query = select(Quest).where(~Quest.id.in_(existing_link_query))
        missing_result = await db_session.execute(missing_quests_query)
        missing_quests = missing_result.scalars().all()

        dirty = False
        for quest in missing_quests:
            db_session.add(self.link_model(quest_id=quest.id, vault_id=vault_id, is_visible=True))
            dirty = True
        if dirty:
            await db_session.commit()

        query = select(Quest).join(self.link_model).where(self.link_model.vault_id == vault_id)
        query = query.offset(skip).limit(limit)
        response = await db_session.execute(query)
        quests = response.scalars().all()

        quest_ids = [q.id for q in quests]
        reqs_by_quest, rewards_by_quest = await _batch_load_quest_details(db_session, quest_ids)

        links_by_quest: dict[UUID4, VaultQuestCompletionLink] = {}
        if quest_ids:
            link_stmt = select(self.link_model).where(
                self.link_model.quest_id.in_(quest_ids),
                self.link_model.vault_id == vault_id,
            )
            link_result = await db_session.execute(link_stmt)
            links_by_quest = {link.quest_id: link for link in link_result.scalars().all()}

        result_items = []
        for quest in quests:
            link = links_by_quest.get(quest.id)
            reqs = reqs_by_quest.get(quest.id, [])
            rewards = rewards_by_quest.get(quest.id, [])

            result_items.append(
                QuestRead(
                    id=quest.id,
                    title=quest.title,
                    short_description=quest.short_description,
                    long_description=quest.long_description,
                    requirements=quest.requirements,
                    rewards=quest.rewards,
                    quest_type=quest.quest_type,
                    quest_category=quest.quest_category,
                    chain_id=quest.chain_id,
                    chain_order=quest.chain_order,
                    created_at=quest.created_at,
                    updated_at=quest.updated_at,
                    is_visible=link.is_visible if link else False,
                    is_completed=link.is_completed if link else False,
                    started_at=link.started_at if link else None,
                    duration_minutes=link.duration_minutes if link else quest.duration_minutes,
                    quest_requirements=[
                        QuestRequirementRead(
                            id=req.id,
                            requirement_type=req.requirement_type,
                            requirement_data=req.requirement_data,
                            is_mandatory=req.is_mandatory,
                        )
                        for req in reqs
                    ],
                    quest_rewards=[
                        QuestRewardRead(
                            id=rew.id,
                            reward_type=rew.reward_type,
                            reward_data=rew.reward_data,
                            reward_chance=rew.reward_chance,
                            item_data=rew.item_data,
                        )
                        for rew in rewards
                    ],
                )
            )

        return result_items

    @staticmethod
    async def create_quest(db_session: AsyncSession, quest_data: QuestCreate) -> Quest:
        quest = Quest(
            title=quest_data.title,
            description=quest_data.description,
            short_description=quest_data.short_description,
            long_description=quest_data.long_description,
            requirements=quest_data.requirements,
            rewards=quest_data.rewards,
        )
        db_session.add(quest)
        await db_session.commit()
        await db_session.refresh(quest)
        return quest

    async def _handle_completion_cascade(
        self, db_session: AsyncSession, db_obj: Quest, vault_id: UUID4
    ) -> list[dict[str, Any]]:
        """Grant rewards when a quest is completed."""
        from app.services.event_bus import GameEvent, event_bus

        granted_rewards: list[dict[str, Any]] = []

        # Grant rewards
        try:
            granted_rewards = await reward_service.process_quest_rewards(db_session, vault_id, db_obj)
            if granted_rewards:
                reward_summary = ", ".join(
                    f"{r.get('amount', r.get('name', r.get('dweller_id', '?')))}" for r in granted_rewards
                )
                logger.info(f"Granted rewards for quest '{db_obj.title}': {reward_summary}")
        except Exception:
            logger.exception(f"Failed to grant rewards for quest '{db_obj.title}'")

        # Emit quest completed event (even if reward processing failed)
        await event_bus.emit(
            GameEvent.QUEST_COMPLETED,
            vault_id,
            {"quest_id": str(db_obj.id), "quest_title": db_obj.title},
        )

        # Send notification
        try:
            vault = await db_session.get(Vault, vault_id)
            if vault and vault.user_id:
                rewards_str = (
                    ", ".join(f"{r.get('amount', r.get('name', r.get('type', '?')))}" for r in granted_rewards)
                    or "no rewards"
                )
                await notification_service.notify_quest_completed(
                    db_session, vault.user_id, vault_id, db_obj.title, rewards_str
                )
        except Exception:
            logger.exception(f"Failed to send quest completion notification for '{db_obj.title}'")

        return granted_rewards

    async def assign_to_vault(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, *, is_visible: bool = True
    ) -> VaultQuestCompletionLink:
        """
        Assign a quest to a vault, making it available for completion.

        Args:
            db_session: Database session
            quest_id: ID of the quest to assign
            vault_id: ID of the vault to assign the quest to
            is_visible: Whether the quest should be visible (default: True)

        Returns:
            VaultQuestCompletionLink: The created link between vault and quest
        """
        # Check if quest exists
        quest = await self.get(db_session, quest_id)
        if not quest:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        # Check if link already exists
        existing_link_query = select(self.link_model).where(
            and_(self.link_model.vault_id == vault_id, self.link_model.quest_id == quest_id)
        )
        result = await db_session.execute(existing_link_query)
        existing_link = result.scalar_one_or_none()

        if existing_link:
            # Update visibility if link exists
            existing_link.is_visible = is_visible
            await db_session.commit()
            await db_session.refresh(existing_link)
            return existing_link

        # Create new link
        link = self.link_model(vault_id=vault_id, quest_id=quest_id, is_visible=is_visible, is_completed=False)
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)
        return link


quest_crud = CRUDQuest(Quest, VaultQuestCompletionLink)
