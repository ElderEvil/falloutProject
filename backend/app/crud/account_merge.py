from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.account_merge import AccountMerge


class CRUDAccountMerge(CRUDBase[AccountMerge, None, None]):
    async def get_by_source(self, db_session: AsyncSession, source_user_id: UUID4) -> AccountMerge | None:
        result = await db_session.execute(select(AccountMerge).where(AccountMerge.source_user_id == source_user_id))
        return result.scalar_one_or_none()

    async def get_by_source_email(self, db_session: AsyncSession, email: str) -> AccountMerge | None:
        """Find an audit row whose source used this email before tombstoning."""
        result = await db_session.execute(
            select(AccountMerge)
            .where(AccountMerge.source_email == email)
            .order_by(AccountMerge.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_source_username(self, db_session: AsyncSession, username: str) -> AccountMerge | None:
        """Find an audit row whose source used this username before tombstoning."""
        result = await db_session.execute(
            select(AccountMerge)
            .where(AccountMerge.source_username == username)
            .order_by(AccountMerge.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db_session: AsyncSession,
        *,
        source_user_id: UUID4,
        target_user_id: UUID4,
        actor_user_id: UUID4,
        source_username: str,
        source_email: str | None,
        target_username: str,
        target_email: str | None,
        reason: str,
        moved_counts: dict[str, int],
        commit: bool = True,
    ) -> AccountMerge:
        db_obj = AccountMerge(
            source_user_id=source_user_id,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            source_username=source_username,
            source_email=source_email,
            target_username=target_username,
            target_email=target_email,
            reason=reason,
            moved_counts=moved_counts,
        )
        db_session.add(db_obj)
        if commit:
            await db_session.commit()
            await db_session.refresh(db_obj)
        else:
            await db_session.flush()
        return db_obj


account_merge = CRUDAccountMerge(AccountMerge)
