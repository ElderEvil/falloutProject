"""CRUD operations for Pregnancy model."""

from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PregnancyStatusEnum
from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.schemas.pregnancy import PregnancyCreate, PregnancyUpdate
from app.utils.exceptions import ResourceNotFoundException


class CRUDPregnancy(CRUDBase[Pregnancy, PregnancyCreate, PregnancyUpdate]):
    """CRUD operations for Pregnancy model."""

    async def get_with_mother(
        self,
        db_session: AsyncSession,
        pregnancy_id: UUID4,
    ) -> tuple[Pregnancy, Dweller]:
        """Get a pregnancy and its mother; callers own any access verification.

        :param db_session: Database session
        :param pregnancy_id: Pregnancy ID to fetch
        :returns: Tuple of (pregnancy, mother) if found
        :raises ResourceNotFoundException: If pregnancy or mother not found
        """
        pregnancy = (await db_session.execute(select(Pregnancy).where(Pregnancy.id == pregnancy_id))).scalars().first()
        if not pregnancy:
            raise ResourceNotFoundException(Pregnancy, identifier=pregnancy_id)

        mother = (await db_session.execute(select(Dweller).where(Dweller.id == pregnancy.mother_id))).scalars().first()
        if not mother:
            raise ResourceNotFoundException(Dweller, identifier=pregnancy.mother_id)

        return pregnancy, mother

    async def get_unavailable_mother_ids(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        cooldown_hours: int,
    ) -> set[UUID4]:
        """Mothers who cannot conceive now: currently pregnant, or delivered
        within the post-birth cooldown window."""
        cooldown_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=cooldown_hours)

        pregnant_query = (
            select(Pregnancy.mother_id)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
        )
        pregnant_ids = set((await db_session.execute(pregnant_query)).scalars().all())

        postpartum_query = (
            select(Pregnancy.mother_id)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.DELIVERED)
            .where(Pregnancy.updated_at.is_not(None))
            .where(Pregnancy.updated_at >= cooldown_start)
        )
        postpartum_ids = set((await db_session.execute(postpartum_query)).scalars().all())

        return pregnant_ids | postpartum_ids

    async def get_due_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[Pregnancy]:
        """Pregnancies in a vault whose due date has passed."""
        query = (
            select(Pregnancy)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
            .where(Pregnancy.due_at <= datetime.now(UTC).replace(tzinfo=None))
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_active_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[Pregnancy]:
        """Active pregnancies for a vault."""
        query = (
            select(Pregnancy)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_active_by_mother(self, db_session: AsyncSession, mother_id: UUID4) -> Pregnancy | None:
        """Active pregnancy of a specific mother, if any."""
        query = select(Pregnancy).where(
            Pregnancy.mother_id == mother_id,
            Pregnancy.status == PregnancyStatusEnum.PREGNANT,
        )
        return (await db_session.execute(query)).scalars().first()

    async def get_all_by_mother_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[Pregnancy]:
        """All pregnancies (any status) whose mother lives in the vault."""
        query = select(Pregnancy).join(Dweller, Pregnancy.mother_id == Dweller.id).where(Dweller.vault_id == vault_id)
        return list((await db_session.execute(query)).scalars().all())

    async def get_active_involving(self, db_session: AsyncSession, dweller_id: UUID4) -> list[Pregnancy]:
        """Active pregnancies where the dweller is the mother or the father."""
        query = select(Pregnancy).where(
            (Pregnancy.mother_id == dweller_id) | (Pregnancy.father_id == dweller_id),
            Pregnancy.status == PregnancyStatusEnum.PREGNANT,
        )
        return list((await db_session.execute(query)).scalars().all())


pregnancy = CRUDPregnancy(Pregnancy)
