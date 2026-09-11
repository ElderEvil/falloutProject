import logging
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.core.event_bus import GameEvent, event_bus
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.services.notification_service import notification_service
from app.services.reward_service import reward_service
from app.utils.quest_duration import effective_quest_duration_minutes
from app.utils.reward_delivery import defer_reward_delivery

logger = logging.getLogger(__name__)


class QuestService:
    async def check_and_complete_quests(self, db_session: AsyncSession, vault_id: UUID4 | None = None) -> int:
        """Mark elapsed quests ready for reward claiming and return their parties."""
        now = datetime.utcnow()
        duration_minutes = func.coalesce(VaultQuestCompletionLink.duration_minutes, Quest.duration_minutes)
        if db_session.bind and db_session.bind.dialect.name == "sqlite":
            expires_at = func.datetime(
                VaultQuestCompletionLink.started_at,
                func.printf("+%s minutes", duration_minutes),
            )
        else:
            expires_at = VaultQuestCompletionLink.started_at + func.make_interval(0, 0, 0, 0, 0, duration_minutes)

        links = await crud.quest_crud.get_expired_party_links(
            db_session, now=now, expires_at=expires_at, vault_id=vault_id
        )

        completed_count = 0
        for link in links:
            try:
                await self.mark_quest_ready_to_claim(db_session, link.quest_id, link.vault_id)
            except Exception:
                # Keep one quest failure isolated; the raw-session completion path is tested end to end.
                logger.exception(f"Failed to auto-complete quest {link.quest_id} for vault {link.vault_id}")
            else:
                completed_count += 1
                logger.info(f"Quest {link.quest_id} is ready to claim for vault {link.vault_id}")

        return completed_count

    async def start_quest(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> VaultQuestCompletionLink:
        """Start a quest or ready a state objective."""
        from app.crud.quest_party import quest_party_crud
        from app.utils.exceptions import (
            AccessDeniedException,
            ResourceConflictException,
            ResourceNotFoundException,
            ValidationException,
        )

        link = await db_session.get(VaultQuestCompletionLink, (vault_id, quest_id))

        if not link:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )

        if link.is_completed:
            raise AccessDeniedException("Quest already completed")
        if link.started_at is not None:
            raise ResourceConflictException("Quest is already in progress")

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if quest.quest_category in ("building", "population", "training"):
            link.is_reward_ready = True
            await db_session.commit()
            await db_session.refresh(link)
            return link
        if quest.duration_minutes is None or quest.duration_minutes <= 0:
            raise ValidationException("Quest duration must be a positive value")

        party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
        if not party:
            raise ValidationException("Assign at least one dweller before starting this quest")

        link.started_at = datetime.utcnow()
        link.is_reward_ready = False
        link.duration_minutes = effective_quest_duration_minutes(quest.duration_minutes)

        await db_session.commit()
        await db_session.refresh(link)

        logger.info(f"Started quest {quest_id} for vault {vault_id} with duration {link.duration_minutes} minutes")
        return link

    async def get_available_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> list[Quest]:
        """Get quests available for a vault, respecting quest chain prerequisites."""
        completed_quest_ids = await crud.quest_crud.get_completed_quest_ids(db_session, vault_id)
        all_quests = await crud.quest_crud.get_visible_quests_for_vault(db_session, vault_id)

        available = [
            quest
            for quest in all_quests
            if quest.previous_quest_id is None or quest.previous_quest_id in completed_quest_ids
        ]

        return available[skip : skip + limit]

    async def mark_quest_ready_to_claim(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Quest:
        """Return a finished party and make its rewards available to claim."""
        from app.crud.quest_party import quest_party_crud
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if link.started_at is None:
            raise ValidationException("Quest must be started before it can be completed")

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        duration = link.duration_minutes if link.duration_minutes is not None else quest.duration_minutes
        if datetime.utcnow() < link.started_at + timedelta(minutes=duration):
            raise ValidationException("Quest is still in progress")
        if link.is_reward_ready:
            return quest

        party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
        for member in party:
            dweller = await db_session.get(Dweller, member.dweller_id)
            if dweller:
                dweller.status = DwellerStatusEnum.IDLE
        link.is_reward_ready = True
        await db_session.commit()

        return quest

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
            await crud.quest_crud.mark_completed(db_session, quest_id=quest_id, vault_id=vault_id)
            granted_rewards = await self._settle_quest_rewards(db_session, quest, vault_id)
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
        from app.crud.quest_party import quest_party_crud

        async with defer_reward_delivery(db_session):
            await db_session.refresh(quest, ["quest_rewards"])
            granted_rewards = await reward_service.process_quest_rewards(db_session, vault_id, quest)
            party = await quest_party_crud.get_party_for_quest(db_session, quest.id, vault_id)
            if party:
                experience_reward = await reward_service.grant_experience(
                    db_session, [member.dweller_id for member in party], quest.duration_minutes * 10
                )
                experience_reward["name"] = "Quest experience"
                granted_rewards.append(experience_reward)

        if granted_rewards:
            summary = ", ".join(f"{r.get('amount', r.get('name', r.get('dweller_id', '?')))}" for r in granted_rewards)
            logger.info(f"Granted rewards for quest '{quest.title}': {summary}")

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
                    dweller = await db_session.get(Dweller, UUID(str(raw_dweller_id)))
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
            vault = await db_session.get(Vault, vault_id)
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
                rewards_str = (
                    ", ".join(
                        f"{reward.get('amount', reward.get('name', reward.get('type', '?')))}"
                        for reward in granted_rewards
                    )
                    or "no rewards"
                )
                await notification_service.notify_quest_completed(
                    db_session, vault.user_id, vault_id, quest.title, rewards_str
                )
        except Exception:
            logger.exception(f"Failed to send quest completion notification for '{quest.title}'")

    async def get_eligible_dwellers(
        self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4
    ) -> list[dict[str, Any]]:
        """Get dwellers eligible for a quest based on requirements."""
        from app.utils.exceptions import ResourceNotFoundException

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        await db_session.refresh(quest, ["quest_requirements"])

        dwellers = await crud.quest_crud.get_quest_eligible_dwellers(db_session, vault_id)

        vault_level_req_types = {"item", "room", "dweller_count", "quest_completed"}
        eligible = []
        for dweller in dwellers:
            meets_req = True
            for req in quest.quest_requirements:
                req_type = req.requirement_type
                req_data = req.requirement_data or {}

                if req_type == "level":
                    required_level = req_data.get("level", 1)
                    if dweller.level < required_level:
                        meets_req = False
                        break
                elif req_type in vault_level_req_types:
                    pass
                else:
                    meets_req = False
                    break

            if meets_req:
                eligible.append(
                    {
                        "id": str(dweller.id),
                        "first_name": dweller.first_name,
                        "last_name": dweller.last_name,
                        "level": dweller.level,
                        "rarity": dweller.rarity,
                    }
                )

        return eligible


quest_service = QuestService()
