from typing import Any

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserUpdate
from app.utils.exceptions import ResourceConflictException


def build_user_model(
    *,
    username: str,
    email: str,
    password: str | None = None,
    is_superuser: bool = False,
) -> User:
    """Build a User row; ``password=None`` creates a provider-only account."""
    return User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password) if password is not None else None,
        is_superuser=is_superuser,
    )


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def get_for_update(self, db_session: SAAsyncSession, user_id: UUID4) -> User | None:
        result = await db_session.execute(
            select(User).where(col(User.id) == user_id).with_for_update().execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, db_session: AsyncSession, email: str, include_deleted: bool = False) -> User | None:
        query = select(self.model).where(self.model.email == email)
        if not include_deleted:
            query = query.where(~col(self.model.is_deleted))
        response = await db_session.execute(query)
        return response.scalar_one_or_none()

    async def get_by_username(
        self, db_session: AsyncSession, username: str, include_deleted: bool = False
    ) -> User | None:
        query = select(self.model).where(self.model.username == username)
        if not include_deleted:
            query = query.where(~col(self.model.is_deleted))
        response = await db_session.execute(query)
        return response.scalar_one_or_none()

    async def create(self, db_session: AsyncSession, obj_in: UserCreate) -> User:
        db_obj = build_user_model(
            username=obj_in.username,
            email=obj_in.email,
            password=obj_in.password,
            is_superuser=obj_in.is_superuser,
        )
        try:
            db_session.add(db_obj)
            await db_session.flush()
            db_session.add(UserProfile(user_id=db_obj.id))
            await db_session.commit()
        except IntegrityError as e:
            await db_session.rollback()
            raise ResourceConflictException(detail="User already exists") from e
        await db_session.refresh(db_obj)
        return db_obj

    async def create_with_oauth_account(
        self,
        db_session: AsyncSession,
        *,
        provider: str,
        provider_user_id: str,
        username: str,
        email: str,
    ) -> tuple[User, OAuthAccount]:
        """Create user, profile, and provider link in one transaction."""
        db_obj = build_user_model(username=username, email=email)
        db_obj.email_verified = True
        link = OAuthAccount(provider=provider, provider_user_id=provider_user_id, user_id=db_obj.id)
        try:
            db_session.add(db_obj)
            # Flush the parent first: oauth_account.user_id has an FK but no ORM
            # relationship, so the unit of work could otherwise insert it first.
            await db_session.flush()
            db_session.add(UserProfile(user_id=db_obj.id))
            db_session.add(link)
            await db_session.commit()
        except IntegrityError as exc:
            await db_session.rollback()
            raise ResourceConflictException(detail="User or OAuth identity already exists") from exc
        await db_session.refresh(db_obj)
        await db_session.refresh(link)
        return db_obj, link

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
        user = await self.get_by_email(db_session, email=email, include_deleted=False)
        if not user or not user.hashed_password:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def is_active(user: User) -> bool:
        return user.is_active and not user.is_deleted

    @staticmethod
    def is_superuser(user: User) -> bool:
        return user.is_superuser


user = CRUDUser(User)
