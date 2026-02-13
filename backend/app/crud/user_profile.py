import logging

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.user_profile import UserProfile, UserProfileBase
from app.schemas.user_profile import ProfileUpdate, ProfileUpdateStatistics

logger = logging.getLogger(__name__)


class CRUDUserProfile(CRUDBase[UserProfile, UserProfileBase, ProfileUpdate]):
    async def get_by_user_id(self, db_session: AsyncSession, user_id: UUID4) -> UserProfile | None:
        """Get profile by user ID."""
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalar_one_or_none()

    async def create_for_user(self, db_session: AsyncSession, user_id: UUID4) -> UserProfile:
        """
        Create a new profile for a user with race condition handling.

        If a concurrent request already created the profile (IntegrityError due to
        unique constraint on user_id), this method rolls back and returns the
        existing profile instead of raising an error.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param user_id: User ID to create profile for
        :type user_id: UUID4
        :returns: The created or existing profile
        :rtype: UserProfile
        """
        db_obj = UserProfile(user_id=user_id)
        db_session.add(db_obj)
        try:
            await db_session.commit()
            await db_session.refresh(db_obj)
        except IntegrityError:
            # Race condition: another request created the profile first
            logger.debug("Profile already exists for user %s, fetching existing", user_id)
            await db_session.rollback()
            # Re-fetch the existing profile
            existing = await self.get_by_user_id(db_session, user_id)
            if existing:
                return existing
            # Should not happen, but re-raise if profile still not found
            raise
        else:
            return db_obj

    async def increment_statistic(
        self,
        db_session: AsyncSession,
        user_id: UUID4,
        stat_name: str,
        amount: int = 1,
    ) -> UserProfile | None:
        """Increment a statistics field."""
        profile = await self.get_by_user_id(db_session, user_id)
        if not profile:
            return None

        current_value = getattr(profile, stat_name, 0)
        new_value = current_value + amount
        update_data = {stat_name: new_value}

        return await self.update(db_session, id=profile.id, obj_in=ProfileUpdateStatistics(**update_data))

    async def update_fields(
        self,
        db_session: AsyncSession,
        user_id: UUID4,
        **kwargs,
    ) -> UserProfile | None:
        """Update multiple profile fields at once."""
        profile = await self.get_by_user_id(db_session, user_id)
        if not profile:
            return None

        return await self.update(db_session, id=profile.id, obj_in=ProfileUpdateStatistics(**kwargs))


profile_crud = CRUDUserProfile(UserProfile)
