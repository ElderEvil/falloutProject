"""CRUD operations for per-vault room-theme ownership."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.vault_theme import VaultTheme


class CRUDVaultTheme(CRUDBase[VaultTheme, None, None]):
    """Queries and ownership writes for themes."""

    async def get_for_vault(self, db_session: AsyncSession, vault_id: UUID4, style: str) -> VaultTheme | None:
        result = await db_session.execute(
            select(VaultTheme).where(VaultTheme.vault_id == vault_id, VaultTheme.style == style)
        )
        return result.scalars().first()

    async def crafted_styles(self, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Styles the vault has crafted, and may therefore apply."""
        result = await db_session.execute(
            select(VaultTheme.style).where(
                VaultTheme.vault_id == vault_id,
                col(VaultTheme.crafted_at).is_not(None),
            )
        )
        return set(result.scalars().all())

    async def is_crafted(self, db_session: AsyncSession, vault_id: UUID4, style: str) -> bool:
        row = await self.get_for_vault(db_session, vault_id, style)
        return row is not None and row.crafted_at is not None

    async def mark_crafted(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        style: str,
        source: str = "craft",
    ) -> VaultTheme:
        """Grant permanent ownership, creating the row when it does not exist."""
        row = await self.get_for_vault(db_session, vault_id, style)
        if row is None:
            row = VaultTheme(
                vault_id=vault_id,
                style=style,
                crafted_at=datetime.utcnow(),
                source=source,
            )
            db_session.add(row)
        elif row.crafted_at is None:
            row.crafted_at = datetime.utcnow()
            row.source = source
            db_session.add(row)
        return row


vault_theme = CRUDVaultTheme(VaultTheme)
