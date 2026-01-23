"""CRUD operations for Pregnancy model."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_user_vault_or_403
from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.models.user import User
from app.schemas.pregnancy import PregnancyCreate, PregnancyUpdate
from app.utils.exceptions import ResourceNotFoundException


class CRUDPregnancy(CRUDBase[Pregnancy, PregnancyCreate, PregnancyUpdate]):
    """CRUD operations for Pregnancy model with vault access verification."""

    async def get_with_vault_access(
        self,
        db_session: AsyncSession,
        pregnancy_id: UUID4,
        user: User,
    ) -> tuple[Pregnancy, Dweller]:
        """
        Get pregnancy and verify user has vault access via mother.

        :param db_session: Database session
        :param pregnancy_id: Pregnancy ID to fetch
        :param user: Current user for access verification
        :returns: Tuple of (pregnancy, mother) if found and user has access
        :raises ResourceNotFoundException: If pregnancy or mother not found
        :raises HTTPException: 403 if user doesn't have vault access
        """
        # Get pregnancy
        query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
        result = await db_session.execute(query)
        preg = result.scalars().first()

        if not preg:
            raise ResourceNotFoundException(Pregnancy, identifier=pregnancy_id)

        # Get mother to verify vault access
        mother_query = select(Dweller).where(Dweller.id == preg.mother_id)
        mother = (await db_session.execute(mother_query)).scalars().first()

        if not mother:
            raise ResourceNotFoundException(Dweller, identifier=preg.mother_id, detail="Mother dweller not found")

        # Verify user has access to the vault (raises 403 if not)
        await get_user_vault_or_403(mother.vault_id, user, db_session)

        return preg, mother


pregnancy = CRUDPregnancy(Pregnancy)
