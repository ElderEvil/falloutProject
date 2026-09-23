import logging
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import func, inspect
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.core.event_bus import GameEvent, event_bus
from app.models.quest import Quest
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import EligibleDwellerRead, QuestRead
from app.schemas.rewards import format_reward_summary, granted_reward_adapter
from app.services.notification_service import notification_service
from app.services.progression.quests import availability
from app.services.progression.quests.availability import QuestAvailability
from app.services.progression.quests.requirements import individual_meets_requirement, party_missing_requirements
from app.services.reward_service import reward_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.quest_duration import effective_quest_duration_minutes, quest_return_leg_minutes
from app.utils.reward_delivery import defer_reward_delivery

logger = logging.getLogger(__name__)


class QuestService:
    async def check_and_complete_quests(self, db_session: AsyncSession, vault_id: UUID4 | None = None) -> int:
        """Start return legs for elapsed quests and finalize parties that arrived home.

        Returns the number of quests finalized (made ready to claim) this run.
        """
        now = datetime.utcnow()
        duration_minutes = func.coalesce(VaultQuestCompletionLink.duration_minutes, Quest.duration_minutes)
        if db_session.bind and db_session.bind.dialect.name == "sqlite":
            expires_at = func.datetime(
                VaultQuestCompletionLink.started_at,
                func.printf("+%s minutes", duration_minutes),
            )
        else:
            expires_at = VaultQuestCompletionLink.started_at + func.make_interval(0, 0, 0, 0, 0, duration_minutes)

        expired_links = await crud.quest_crud.get_expired_party_links(
            db_session, now=now, expires_at=expires_at, vault_id=vault_id
        )
        for link in expired_links:
            try:
                await self.start_quest_return(db_session, link.quest_id, link.vault_id)
            except Exception:
                # Keep one quest failure isolated; the raw-session completion path is tested end to end.
                logger.exception(f"Failed to start return for quest {link.quest_id} for vault {link.vault_id}")
            else:
                logger.info(f"Quest {link.quest_id} party is travelling home for vault {link.vault_id}")

        arrived_links = await crud.quest_crud.get_arrived_party_links(db_session, now=now, vault_id=vault_id)
        completed_count = 0
        for link in arrived_links:
            try:
                await self.mark_quest_ready_to_claim(db_session, link.quest_id, link.vault_id)
            except Exception:
                # Keep one quest failure isolated; the raw-session completion path is tested end to end.
                logger.exception(f"Failed to auto-complete quest {link.quest_id} for vault {link.vault_id}")
            else:
                completed_count += 1
                logger.info(f"Quest {link.quest_id} is ready to claim for vault {link.vault_id}")

        return completed_count

    async def start_quest_return(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4
    ) -> VaultQuestCompletionLink:
        """Send a finished quest party home; rewards wait until they arrive."""
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = await crud.quest_crud.get_link_for_update(db_session, quest_id=quest_id, vault_id=vault_id)
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if link.started_at is None:
            raise ValidationException("Quest must be started before it can be completed")
        if link.is_completed or link.is_reward_ready:
            raise ValidationException("Quest party is already home")
        if link.return_completes_at is not None:
            raise ValidationException("Party is already travelling home")

        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        duration = link.duration_minutes if link.duration_minutes is not None else quest.duration_minutes
        if datetime.utcnow() < link.started_at + timedelta(minutes=duration):
            raise ValidationException("Quest is still in progress")

        link.start_return(quest_return_leg_minutes(duration))
        await db_session.commit()
        await db_session.refresh(link)

        logger.info(f"Quest {quest_id} party started travelling home for vault {vault_id}")
        return link

    async def start_quest(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> VaultQuestCompletionLink:
        """Start a quest or ready a state objective."""
        from app.utils.exceptions import (
            AccessDeniedException,
            ResourceConflictException,
            ResourceNotFoundException,
            ValidationException,
        )

        link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)

        if not link:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )

        if link.is_completed:
            raise AccessDeniedException("Quest already completed")
        if link.started_at is not None:
            raise ResourceConflictException("Quest is already in progress")

        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if quest.quest_category in ("building", "population", "training"):
            link.is_reward_ready = True
            await db_session.commit()
            await db_session.refresh(link)
            return link
        if quest.duration_minutes is None or quest.duration_minutes <= 0:
            raise ValidationException("Quest duration must be a positive value")

        members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)
        if not members:
            raise ValidationException("Assign at least one dweller before starting this quest")

        state = inspect(quest)
        if state is not None and "quest_requirements" in state.unloaded:
            await db_session.refresh(quest, ["quest_requirements"])
        party_dwellers = await crud.team_crud.get_quest_team_dwellers(db_session, quest_id, vault_id)
        missing = party_missing_requirements(party_dwellers, quest)
        if missing:
            raise ValidationException("; ".join(missing))

        link.started_at = datetime.utcnow()
        link.is_reward_ready = False
        link.duration_minutes = effective_quest_duration_minutes(quest.duration_minutes)

        await db_session.commit()
        await db_session.refresh(link)

        logger.info(f"Started quest {quest_id} for vault {vault_id} with duration {link.duration_minutes} minutes")
        return link

    async def start_quest_for_vault(self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4) -> Quest:
        """Start a quest for a vault, checking availability first.

        The whole start workflow lives here so the router only authorizes and
        delegates.

        Raises:
            ResourceNotFoundException: If the quest does not exist.
            ValidationException: If the quest is not currently available.
        """
        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        await db_session.refresh(quest, ["quest_requirements"])

        availability = await self.get_quest_availability(db_session, vault_id, quest)
        if not availability.available:
            detail = (
                f"Missing requirements: {', '.join(availability.missing)}"
                if availability.missing
                else (availability.lock_reason or "Quest is not available")
            )
            raise ValidationException(detail=detail)

        await self.start_quest(db_session, quest_id, vault_id)
        await db_session.refresh(quest, ["quest_requirements", "quest_rewards"])
        return quest

    async def get_quest_availability(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        quest: Quest,
        *,
        has_office: bool | None = None,
        completed_quest_ids: set[UUID4] | None = None,
        resolve_quest: Callable[[UUID4], Quest | None] | None = None,
    ) -> QuestAvailability:
        """Whether a vault can start a quest; delegates to the availability policy."""
        return await availability.quest_availability(
            db_session,
            vault_id,
            quest,
            has_office=has_office,
            completed_quest_ids=completed_quest_ids,
            resolve_quest=resolve_quest,
        )

    async def get_quests_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
        available_only: bool = False,
    ) -> Sequence[QuestRead]:
        """Vault quest read; delegates to the availability policy."""
        return await availability.get_quests_for_vault(db_session, vault_id, skip, limit, available_only)

    async def mark_quest_ready_to_claim(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Quest:
        """Return a finished party and make its rewards available to claim."""
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = await crud.quest_crud.get_link_for_update(db_session, quest_id=quest_id, vault_id=vault_id)
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if link.started_at is None:
            raise ValidationException("Quest must be started before it can be completed")

        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if link.is_reward_ready:
            return quest
        if link.return_completes_at is None:
            raise ValidationException("Party has not been sent home")
        if datetime.utcnow() < link.return_completes_at:
            raise ValidationException("Party is still travelling home")

        members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)
        for member in members:
            dweller = await crud.dweller.get_or_none(db_session, member.dweller_id, include_deleted=True)
            if dweller:
                dweller.status = DwellerStatusEnum.IDLE
        link.is_reward_ready = True
        await db_session.commit()

        await self._announce_quest_arrival(db_session, quest, vault_id)
        return quest

    async def _announce_quest_arrival(self, db_session: AsyncSession, quest: Quest, vault_id: UUID4) -> None:
        """Best-effort arrival notification when a quest party returns home."""
        try:
            vault = await crud.vault.get_or_none(db_session, vault_id, include_deleted=True)
            if vault and vault.user_id:
                await notification_service.notify_quest_party_returned(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault_id,
                    quest_id=quest.id,
                    quest_title=quest.title,
                )
        except Exception:
            logger.exception(f"Failed to send quest arrival notification for '{quest.title}'")

    async def claim_quest_rewards(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4
    ) -> tuple[Quest, list[Any]]:
        """Atomically deliver rewards that a returning party has made claimable."""
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if not link.is_reward_ready:
            raise ValidationException("Quest rewards are not ready to claim")

        quest = None
        try:
            quest = await crud.quest_crud.get(db_session, quest_id)
            completed_link = await crud.quest_crud.mark_completed(db_session, quest_id=quest_id, vault_id=vault_id)
            granted_rewards = await self._settle_quest_rewards(db_session, quest, vault_id)
            completed_link.granted_rewards = [
                granted_reward_adapter.validate_python(reward).model_dump(mode="json") for reward in granted_rewards
            ]
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            if quest is not None:
                with suppress(Exception):
                    await db_session.refresh(quest)
            raise

        await self._announce_quest_completion(db_session, quest, vault_id, granted_rewards)
        return quest, granted_rewards

    async def _settle_quest_rewards(
        self, db_session: AsyncSession, quest: Quest, vault_id: UUID4
    ) -> list[dict[str, Any]]:
        """Grant every quest reward within the completion transaction."""
        async with defer_reward_delivery(db_session):
            await db_session.refresh(quest, ["quest_rewards"])
            granted_rewards = await reward_service.process_quest_rewards(db_session, vault_id, quest)
            members = await crud.team_crud.get_quest_team(db_session, quest.id, vault_id)
            if members:
                experience_reward = await reward_service.grant_experience(
                    db_session, [member.dweller_id for member in members], quest.duration_minutes * 10
                )
                experience_reward["name"] = "Quest experience"
                granted_rewards.append(experience_reward)

        if granted_rewards:
            granted_models = [granted_reward_adapter.validate_python(reward) for reward in granted_rewards]
            logger.info(f"Granted rewards for quest '{quest.title}': {format_reward_summary(granted_models)}")

        return granted_rewards

    async def _announce_quest_completion(
        self, db_session: AsyncSession, quest: Quest, vault_id: UUID4, granted_rewards: list[dict[str, Any]]
    ) -> None:
        """Publish reward and completion feedback after successful settlement."""

        async def emit(event: GameEvent, payload: dict[str, Any]) -> None:
            await event_bus.emit(event, vault_id, payload)

        leveled_up_dwellers = []
        for reward in granted_rewards:
            kind = reward["reward_type"]
            if kind == "caps":
                await emit(GameEvent.RESOURCE_COLLECTED, {"resource_type": "caps", "amount": reward["amount"]})
            elif kind in ("item", "stimpak"):
                item_type = "stimpak" if kind == "stimpak" else reward.get("item_type", "item")
                await emit(GameEvent.ITEM_COLLECTED, {"item_type": item_type, "amount": reward.get("amount", 1)})
            elif kind == "experience":
                for raw_dweller_id in reward["leveled_up"]:
                    dweller = await crud.dweller.get_or_none(
                        db_session, UUID(str(raw_dweller_id)), include_deleted=True
                    )
                    if dweller:
                        leveled_up_dwellers.append(dweller)
                        await emit(
                            GameEvent.DWELLER_LEVEL_UP,
                            {
                                "dweller_id": str(dweller.id),
                                "level": dweller.level,
                                "old_level": dweller.level - 1,
                                "amount": 1,
                            },
                        )

        await emit(
            GameEvent.QUEST_COMPLETED,
            {"quest_id": str(quest.id), "quest_title": quest.title, "quest_type": quest.quest_type.value},
        )

        try:
            vault = await crud.vault.get_or_none(db_session, vault_id, include_deleted=True)
            if vault and vault.user_id:
                for dweller in leveled_up_dwellers:
                    await notification_service.notify_level_up(
                        db_session,
                        user_id=vault.user_id,
                        vault_id=vault_id,
                        dweller_id=dweller.id,
                        dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                        new_level=dweller.level,
                        meta_data={"old_level": dweller.level - 1, "new_level": dweller.level},
                    )
        except Exception:
            logger.exception(f"Failed to send quest completion notification for '{quest.title}'")

    async def get_eligible_dwellers(
        self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4
    ) -> list[EligibleDwellerRead]:
        """Dwellers who individually satisfy the quest's party-level requirement gates.

        A candidate is eligible when they meet every per-individual threshold
        (LEVEL/ITEM/ATTACK/STAT), independent of the gate's aggregate ``count`` —
        two qualifying dwellers are both eligible for a ``count: 2`` gate. Vault-level
        gates (ROOM/DWELLER_COUNT/QUEST_COMPLETED) are checked on the start path, so
        they do not filter candidates here.
        """
        from app.utils.exceptions import ResourceNotFoundException

        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        await db_session.refresh(quest, ["quest_requirements"])

        dwellers = await crud.quest_crud.get_quest_eligible_dwellers(db_session, vault_id)

        return [
            EligibleDwellerRead(
                id=dweller.id,
                first_name=dweller.first_name,
                last_name=dweller.last_name,
                level=dweller.level,
                rarity=dweller.rarity,
            )
            for dweller in dwellers
            if all(individual_meets_requirement(dweller, req) for req in quest.quest_requirements)
        ]


quest_service = QuestService()
