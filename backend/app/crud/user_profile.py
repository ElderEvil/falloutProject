import logging
from collections.abc import Iterable
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.user_profile import UserProfile, UserProfileBase
from app.schemas.user_profile import ProfileUpdate, ProfileUpdateStatistics

logger = logging.getLogger(__name__)


class CRUDUserProfile(CRUDBase[UserProfile, UserProfileBase, ProfileUpdate]):
    async def get_by_user_id(self, db_session: AsyncSession, user_id: UUID) -> UserProfile | None:
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalar_one_or_none()

    async def create_for_user(self, db_session: AsyncSession, user_id: UUID) -> UserProfile:
        """Stage a profile for ``user_id``; the caller owns the transaction.

        Race-safe: on a unique violation from a concurrent create, the savepoint rolls back
        only this attempt and the existing profile is returned instead of raising.
        """
        db_obj = UserProfile(user_id=user_id)
        try:
            async with db_session.begin_nested():
                db_session.add(db_obj)
                await db_session.flush()
        except IntegrityError:
            logger.debug("Profile already exists for user %s, fetching existing", user_id)
            existing = await self.get_by_user_id(db_session, user_id)
            if existing:
                return existing
            # Should not happen, but re-raise if profile still not found
            raise
        return db_obj

    async def lock_by_user_ids(self, db_session: AsyncSession, user_ids: Iterable[UUID]) -> list[UserProfile]:
        """Lock the participants' profiles in profile-id order for a merge."""
        result = await db_session.execute(
            select(self.model)
            .where(col(self.model.user_id).in_(list(user_ids)))
            .order_by(col(self.model.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def create_staged(self, db_session: AsyncSession, user_id: UUID) -> UserProfile:
        """Add a profile and flush it without committing; the caller owns the transaction."""
        db_obj = UserProfile(user_id=user_id)
        db_session.add(db_obj)
        await db_session.flush()
        return db_obj

    async def reassign_user(
        self, db_session: AsyncSession, source_user_id: UUID, target_user_id: UUID, *, commit: bool = True
    ) -> int:
        result = await db_session.execute(
            update(self.model)
            .where(col(self.model.user_id) == source_user_id)
            .values(user_id=target_user_id)
            .execution_options(synchronize_session=False)
        )
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        return cast("CursorResult", result).rowcount or 0

    async def delete_for_user(self, db_session: AsyncSession, user_id: UUID, *, commit: bool = True) -> int:
        result = await db_session.execute(
            delete(self.model).where(col(self.model.user_id) == user_id).execution_options(synchronize_session=False)
        )
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        return cast("CursorResult", result).rowcount or 0

    async def increment_statistic(
        self,
        db_session: AsyncSession,
        user_id: UUID,
        stat_name: str,
        amount: int = 1,
        *,
        commit: bool = True,
    ) -> UserProfile | None:
        """Atomically increment an allowlisted statistics field."""
        if stat_name not in ProfileUpdateStatistics.model_fields:
            raise ValueError(f"Unsupported profile statistic: {stat_name}")

        column = getattr(self.model, stat_name)
        result = await db_session.execute(
            update(self.model).where(self.model.user_id == user_id).values({column: column + amount})
        )
        if result.rowcount == 0:
            return None

        if commit:
            await db_session.commit()
            return await self.get_by_user_id(db_session, user_id)
        return None


profile_crud = CRUDUserProfile(UserProfile)
