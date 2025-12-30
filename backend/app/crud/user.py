from typing import Any

from fastapi import HTTPException
from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def get_by_email(self, db_session: AsyncSession, email: str) -> User | None:
        response = await db_session.execute(select(self.model).where(self.model.email == email))
        return response.scalar_one_or_none()

    async def get_by_username(self, db_session: AsyncSession, username: str) -> User | None:
        response = await db_session.execute(select(self.model).where(self.model.username == username))
        return response.scalar_one_or_none()

    async def create(self, db_session: AsyncSession, obj_in: UserCreate) -> User:
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            is_superuser=obj_in.is_superuser,
        )
        try:
            db_session.add(db_obj)
            await db_session.commit()
            await db_session.refresh(db_obj)

            # Auto-create user profile
            profile = UserProfile(user_id=db_obj.id)
            db_session.add(profile)
            await db_session.commit()
        except IntegrityError as e:
            await db_session.rollback()
            raise HTTPException(
                status_code=409,
                detail="User already exists",
            ) from e
        return db_obj

    async def update(
        self,
        db_session: AsyncSession,
        id: int | UUID4,
        obj_in: UserUpdate | dict[str, Any],
    ) -> User:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        if update_data.get("password"):
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        return await super().update(db_session, id=id, obj_in=update_data)

    async def authenticate(self, db_session: AsyncSession, *, email: str, password: str) -> User | None:
        user = await self.get_by_email(db_session, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def is_active(user: User) -> bool:
        return user.is_active

    @staticmethod
    def is_superuser(user: User) -> bool:
        return user.is_superuser


user = CRUDUser(User)
