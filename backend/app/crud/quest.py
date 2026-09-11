from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.crud.vault_mixin import VaultActionsMixin
from app.models import Vault
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.quest_reward import QuestReward
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate, QuestRead, QuestRequirementRead, QuestRewardRead, QuestUpdate
from app.utils.exceptions import ResourceNotFoundException
from app.utils.quest_duration import effective_quest_duration_minutes


def _previous_quest_id(quest: Quest, requirements: list[QuestRequirement]) -> UUID4 | str | None:
    """Return a quest's explicit or requirement-derived chain predecessor."""
    if quest.previous_quest_id:
        return quest.previous_quest_id
    return next(
        (
            requirement.requirement_data.get("quest_id")
            for requirement in requirements
            if requirement.is_mandatory
            and requirement.requirement_type == RequirementType.QUEST_COMPLETED
            and requirement.requirement_data.get("quest_id")
        ),
        None,
    )


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
                    duration_minutes=effective_quest_duration_minutes(quest.duration_minutes),
                    previous_quest_id=quest.previous_quest_id,
                    next_quest_id=quest.next_quest_id,
                    created_at=quest.created_at,
                    updated_at=quest.updated_at,
                    is_visible=True,
                    is_completed=False,
                    is_reward_ready=False,
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

        completed_link_stmt = select(self.link_model.quest_id).where(
            self.link_model.vault_id == vault_id,
            self.link_model.is_completed.is_(True),
        )
        completed_link_result = await db_session.execute(completed_link_stmt)
        completed_quest_ids = {str(quest_id) for quest_id in completed_link_result.scalars().all()}

        result_items = []
        for quest in quests:
            link = links_by_quest.get(quest.id)
            reqs = reqs_by_quest.get(quest.id, [])
            rewards = rewards_by_quest.get(quest.id, [])
            previous_quest_id = _previous_quest_id(quest, reqs)
            is_unlocked = previous_quest_id is None or str(previous_quest_id) in completed_quest_ids

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
                    previous_quest_id=previous_quest_id,
                    next_quest_id=quest.next_quest_id,
                    created_at=quest.created_at,
                    updated_at=quest.updated_at,
                    is_visible=(link.is_visible if link else False) and is_unlocked,
                    is_completed=link.is_completed if link else False,
                    is_reward_ready=link.is_reward_ready if link else False,
                    started_at=link.started_at if link else None,
                    duration_minutes=link.duration_minutes
                    if link and link.duration_minutes is not None
                    else effective_quest_duration_minutes(quest.duration_minutes),
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

    async def mark_completed(
        self, db_session: AsyncSession, *, quest_id: UUID4, vault_id: UUID4
    ) -> VaultQuestCompletionLink:
        """Lock and claim a quest link before its rewards settle (persistence only)."""
        return await self._mark_as_complete(db_session=db_session, vault_id=vault_id, quest_entity_id=quest_id)

    async def get_started_state_objective_links(self, db_session: AsyncSession) -> list[VaultQuestCompletionLink]:
        """Started, incomplete, unclaimed links for building/population/training quests (backfill input)."""
        query = (
            select(VaultQuestCompletionLink)
            .join(Quest)
            .where(
                Quest.quest_category.in_(("building", "population", "training")),
                VaultQuestCompletionLink.started_at.is_not(None),
                ~VaultQuestCompletionLink.is_completed,
                ~VaultQuestCompletionLink.is_reward_ready,
            )
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_expired_party_links(
        self,
        db_session: AsyncSession,
        *,
        now: Any,
        expires_at: Any,
        vault_id: UUID4 | None = None,
    ) -> list[VaultQuestCompletionLink]:
        """Started, unfinished links whose quest duration has elapsed, optionally per vault."""
        conditions = [
            ~VaultQuestCompletionLink.is_completed,
            ~VaultQuestCompletionLink.is_reward_ready,
            VaultQuestCompletionLink.started_at.isnot(None),
            expires_at <= now,
        ]
        if vault_id is not None:
            conditions.append(VaultQuestCompletionLink.vault_id == vault_id)
        return list(
            (await db_session.execute(select(VaultQuestCompletionLink).join(Quest).where(*conditions))).scalars().all()
        )

    async def get_completed_quest_ids(self, db_session: AsyncSession, vault_id: UUID4) -> set[UUID4]:
        """IDs of quests the vault has completed."""
        result = await db_session.execute(
            select(VaultQuestCompletionLink.quest_id).where(
                VaultQuestCompletionLink.vault_id == vault_id,
                VaultQuestCompletionLink.is_completed.is_(True),
            )
        )
        return set(result.scalars().all())

    async def get_visible_quests_for_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[Quest]:
        """Quests with a visible link for the vault, requirements/rewards eager-loaded."""
        result = await db_session.execute(
            select(Quest)
            .options(selectinload(Quest.quest_requirements), selectinload(Quest.quest_rewards))
            .join(
                VaultQuestCompletionLink,
                and_(Quest.id == VaultQuestCompletionLink.quest_id, VaultQuestCompletionLink.vault_id == vault_id),
            )
            .where(VaultQuestCompletionLink.is_visible)
        )
        return list(result.scalars().all())

    async def get_link(
        self, db_session: AsyncSession, *, quest_id: UUID4, vault_id: UUID4
    ) -> VaultQuestCompletionLink | None:
        """The vault's completion link for a quest, or None."""
        result = await db_session.execute(
            select(VaultQuestCompletionLink).where(
                VaultQuestCompletionLink.quest_id == quest_id,
                VaultQuestCompletionLink.vault_id == vault_id,
            )
        )
        return result.scalars().one_or_none()

    async def get_quest_eligible_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        """Adult, unassigned dwellers of a vault eligible for quest assignment."""
        result = await db_session.execute(
            select(Dweller).where(
                Dweller.vault_id == vault_id,
                ~Dweller.is_deleted,
                Dweller.is_adult,
                Dweller.age_group == AgeGroupEnum.ADULT,
                Dweller.status.notin_([DwellerStatusEnum.QUESTING, DwellerStatusEnum.EXPLORING]),
            )
        )
        return list(result.scalars().all())

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
