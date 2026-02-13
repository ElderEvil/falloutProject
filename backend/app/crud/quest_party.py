import logging
from uuid import UUID

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_party import QuestParty
from app.models.vault import Vault

logger = logging.getLogger(__name__)


class CRUDQuestParty(CRUDBase[QuestParty, None, None]):
    async def assign_party(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[QuestParty]:
        """Assign dwellers to a quest."""
        quest = await db_session.get(Quest, quest_id)
        if not quest:
            raise ValueError(f"Quest {quest_id} not found")

        vault = await db_session.get(Vault, vault_id)
        if not vault:
            raise ValueError(f"Vault {vault_id} not found")

        existing_query = select(QuestParty).where(
            QuestParty.quest_id == quest_id,
            QuestParty.vault_id == vault_id,
        )
        existing_result = await db_session.execute(existing_query)
        existing_party = existing_result.scalars().all()
        for member in existing_party:
            await db_session.delete(member)
        await db_session.flush()

        party_members = []
        for i, dweller_id in enumerate(dweller_ids):
            dweller = await db_session.get(Dweller, dweller_id)
            if not dweller:
                raise ValueError(f"Dweller {dweller_id} not found")
            if dweller.vault_id != vault_id:
                raise ValueError(f"Dweller {dweller_id} does not belong to vault {vault_id}")

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
        result = await db_session.execute(query)
        return list(result.scalars().all())

    async def get_available_dwellers(self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4) -> list[Dweller]:
        """Get dwellers not currently on this quest."""
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
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
