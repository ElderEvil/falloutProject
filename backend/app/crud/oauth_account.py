"""CRUD operations for provider identities."""

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.oauth_account import OAuthAccount
from app.utils.exceptions import ResourceConflictException


class CRUDOAuthAccount:
    async def get_by_provider_subject(
        self, db_session: AsyncSession, provider: str, provider_user_id: str
    ) -> OAuthAccount | None:
        query = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_user(self, db_session: AsyncSession, user_id: UUID4, provider: str) -> OAuthAccount | None:
        query = select(OAuthAccount).where(OAuthAccount.user_id == user_id, OAuthAccount.provider == provider)
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def link_to_user(
        self, db_session: AsyncSession, *, user_id: UUID4, provider: str, provider_user_id: str
    ) -> OAuthAccount:
        link = OAuthAccount(provider=provider, provider_user_id=provider_user_id, user_id=user_id)
        db_session.add(link)
        try:
            await db_session.commit()
        except IntegrityError as exc:
            await db_session.rollback()
            raise ResourceConflictException(detail="OAuth identity already linked") from exc
        await db_session.refresh(link)
        return link


oauth_account = CRUDOAuthAccount()
