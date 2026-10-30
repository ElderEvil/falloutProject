"""CRUD operations for provider identities."""

from typing import cast

from pydantic import UUID4
from sqlalchemy import CursorResult, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select, update
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

    async def list_by_user(self, db_session: AsyncSession, user_id: UUID4) -> list[OAuthAccount]:
        """Provider links for a user, ordered by provider for conflict checks."""
        result = await db_session.execute(
            select(OAuthAccount).where(col(OAuthAccount.user_id) == user_id).order_by(col(OAuthAccount.provider))
        )
        return list(result.scalars().all())

    async def count_by_user(self, db_session: AsyncSession, user_id: UUID4) -> int:
        """Count provider links owned by a user."""
        result = await db_session.execute(
            select(func.count()).select_from(OAuthAccount).where(col(OAuthAccount.user_id) == user_id)
        )
        return int(result.scalar_one())

    async def reassign_user(
        self, db_session: AsyncSession, source_user_id: UUID4, target_user_id: UUID4, *, commit: bool = True
    ) -> int:
        """Move every source provider link to the target; conflict policy lives in the service."""
        result = await db_session.execute(
            update(OAuthAccount)
            .where(col(OAuthAccount.user_id) == source_user_id)
            .values(user_id=target_user_id)
            .execution_options(synchronize_session=False)
        )
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        return cast("CursorResult", result).rowcount or 0

    async def link_to_user(
        self,
        db_session: AsyncSession,
        *,
        user_id: UUID4,
        provider: str,
        provider_user_id: str,
        commit: bool = True,
    ) -> OAuthAccount:
        link = OAuthAccount(provider=provider, provider_user_id=provider_user_id, user_id=user_id)
        db_session.add(link)
        try:
            if commit:
                await db_session.commit()
            else:
                await db_session.flush()
        except IntegrityError as exc:
            await db_session.rollback()
            raise ResourceConflictException(detail="OAuth identity already linked") from exc
        if commit:
            await db_session.refresh(link)
        return link

    async def delete_link(self, db_session: AsyncSession, link: OAuthAccount, *, commit: bool = True) -> None:
        await db_session.delete(link)
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()


oauth_account = CRUDOAuthAccount()
