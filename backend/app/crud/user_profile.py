from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.user_profile import UserProfile, UserProfileBase
from app.schemas.user_profile import ProfileUpdate, ProfileUpdateStatistics


class CRUDUserProfile(CRUDBase[UserProfile, UserProfileBase, ProfileUpdate]):
    async def get_by_user_id(self, db_session: AsyncSession, user_id: UUID4) -> UserProfile | None:
        """Get profile by user ID."""
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalar_one_or_none()

    async def create_for_user(self, db_session: AsyncSession, user_id: UUID4) -> UserProfile:
        """Create a new profile for a user."""
        db_obj = UserProfile(user_id=user_id)
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
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

    async def update_statistics(
        self,
        db_session: AsyncSession,
        user_id: UUID4,
        **kwargs,
    ) -> UserProfile | None:
        """Update multiple statistics at once."""
        profile = await self.get_by_user_id(db_session, user_id)
        if not profile:
            return None

        return await self.update(db_session, id=profile.id, obj_in=ProfileUpdateStatistics(**kwargs))


profile_crud = CRUDUserProfile(UserProfile)
