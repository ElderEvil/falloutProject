import logging

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_party import QuestParty
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum
from app.utils.exceptions import ResourceConflictException

logger = logging.getLogger(__name__)


class CRUDQuestParty(CRUDBase[QuestParty, None, None]):
    async def assign_party(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[QuestParty]:
        """Assign dwellers to a quest."""
        if len(dweller_ids) > 3 or len(dweller_ids) < 1:
            raise ValueError("Party size must be 1-3")

        if not await db_session.get(Quest, quest_id):
            raise ValueError(f"Quest {quest_id} not found")

        if not await db_session.get(Vault, vault_id):
            raise ValueError(f"Vault {vault_id} not found")
        if (link := await db_session.get(VaultQuestCompletionLink, (vault_id, quest_id))) and (
            link.started_at is not None or link.is_reward_ready or link.is_completed
        ):
            raise ResourceConflictException("Quest is already in progress")

        existing_query = select(QuestParty).where(
            QuestParty.quest_id == quest_id,
            QuestParty.vault_id == vault_id,
        )
        existing_party = (await db_session.execute(existing_query)).scalars().all()
        existing_dweller_ids = {member.dweller_id for member in existing_party}

        # Validate the full replacement before clearing the current party.
        dwellers_by_id = {}
        for dweller_id in dweller_ids:
            dweller = await db_session.get(Dweller, dweller_id)
            if not dweller:
                raise ValueError(f"Dweller {dweller_id} not found")
            if dweller.is_deleted:
                raise ValueError(f"Deleted dweller {dweller_id} cannot join a quest")
            if dweller.vault_id != vault_id:
                raise ValueError(f"Dweller {dweller_id} does not belong to vault {vault_id}")
            if not dweller.is_adult or dweller.age_group != AgeGroupEnum.ADULT:
                raise ValueError(f"Child dweller {dweller_id} cannot join a quest")
            if dweller.status == DwellerStatusEnum.EXPLORING:
                raise ValueError(f"Dweller {dweller_id} is exploring and cannot join a quest")
            if dweller.status == DwellerStatusEnum.QUESTING and dweller_id not in existing_dweller_ids:
                raise ValueError(f"Dweller {dweller_id} is already on a quest")
            dwellers_by_id[dweller_id] = dweller

        for member in existing_party:
            dweller = await db_session.get(Dweller, member.dweller_id)
            if dweller:
                dweller.status = DwellerStatusEnum.IDLE
            await db_session.delete(member)
        await db_session.flush()

        party_members = []
        for i, dweller_id in enumerate(dweller_ids):
            dweller = dwellers_by_id[dweller_id]
            dweller.status = DwellerStatusEnum.QUESTING

            party = QuestParty(
                quest_id=quest_id,
                vault_id=vault_id,
                dweller_id=dweller_id,
                slot_number=i + 1,
                status="assigned",
            )
            db_session.add(party)
            party_members.append(party)

        await db_session.commit()
        for pm in party_members:
            await db_session.refresh(pm)

        logger.info(f"Assigned {len(party_members)} dwellers to quest {quest_id}")
        return party_members

    async def get_party_for_quest(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> list[QuestParty]:
        """Get all party members for a quest."""
        query = select(QuestParty).where(
            QuestParty.quest_id == quest_id,
            QuestParty.vault_id == vault_id,
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_available_dwellers(self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4) -> list[Dweller]:
        """Get dwellers not currently on this quest."""
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(~Dweller.is_deleted)
            .where(Dweller.is_adult)
            .where(Dweller.age_group == AgeGroupEnum.ADULT)
            .where(Dweller.status.notin_([DwellerStatusEnum.QUESTING, DwellerStatusEnum.EXPLORING]))
            .where(
                Dweller.id.notin_(
                    select(QuestParty.dweller_id).where(
                        QuestParty.quest_id == quest_id,
                        QuestParty.vault_id == vault_id,
                        QuestParty.status.in_(["assigned", "in_progress"]),
                    )
                )
            )
        )
        result = await db_session.execute(query)
        return list(result.scalars().all())


quest_party_crud = CRUDQuestParty(QuestParty)
