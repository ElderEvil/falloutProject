"""Queries for pvp duels and party rosters; rules live in pvp_duel_service."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PvpDuelStatus
from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.pvp_duel import PvpDuel
from app.models.vault import Vault


class CRUDPvpDuel(CRUDBase[PvpDuel, None, None]):
    """Row access for duels plus the roster and vault-name lookups the service needs."""

    async def get_duel(self, db_session: AsyncSession, duel_id: UUID) -> PvpDuel | None:
        result = await db_session.execute(select(self.model).where(self.model.id == duel_id))
        return result.scalar_one_or_none()

    async def get_for_update(self, db_session: AsyncSession, duel_id: UUID) -> PvpDuel | None:
        """Row lock so two accepts serialize; populate_existing defeats a stale identity-map row."""
        result = await db_session.execute(
            select(self.model)
            .where(self.model.id == duel_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_open_by_challenger(self, db_session: AsyncSession, vault_id: UUID) -> list[PvpDuel]:
        result = await db_session.execute(
            select(self.model).where(
                self.model.challenger_vault_id == vault_id,
                self.model.status == PvpDuelStatus.OPEN,
            )
        )
        return list(result.scalars().all())

    async def list_open_board(self, db_session: AsyncSession, viewer_vault_id: UUID) -> list[PvpDuel]:
        """Open challenges visible to a vault: untargeted ones plus ones aimed at it, never its own."""
        result = await db_session.execute(
            select(self.model)
            .where(
                self.model.status == PvpDuelStatus.OPEN,
                self.model.challenger_vault_id != viewer_vault_id,
                or_(
                    col(self.model.defender_vault_id).is_(None),
                    col(self.model.defender_vault_id) == viewer_vault_id,
                ),
            )
            .order_by(col(self.model.expires_at))
        )
        return list(result.scalars().all())

    async def get_party(
        self, db_session: AsyncSession, vault_id: UUID, dweller_ids: list[UUID] | None
    ) -> list[Dweller]:
        """Living dwellers of one vault, optionally narrowed to ids, with weapon/outfit loaded."""
        query = (
            select(Dweller)
            .where(
                Dweller.vault_id == vault_id,
                ~Dweller.is_deleted,
                ~Dweller.is_dead,
            )
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit))
        )
        if dweller_ids is not None:
            query = query.where(col(Dweller.id).in_(dweller_ids))
        return list((await db_session.execute(query)).scalars().all())

    async def lock_vault(self, db_session: AsyncSession, vault_id: UUID) -> None:
        """Serialize posts per vault so the open-slot check cannot race itself."""
        await db_session.execute(select(Vault.id).where(Vault.id == vault_id).with_for_update())

    async def expire_open(self, db_session: AsyncSession, duel_ids: list[UUID], now: datetime) -> None:
        """Expire only rows that are still OPEN and past due: a concurrent accept must survive."""
        if not duel_ids:
            return
        await db_session.execute(
            update(self.model)
            .where(
                col(self.model.id).in_(duel_ids),
                self.model.status == PvpDuelStatus.OPEN,
                self.model.expires_at <= now,
            )
            .values(status=PvpDuelStatus.EXPIRED)
        )

    async def get_vault(self, db_session: AsyncSession, vault_id: UUID) -> Vault | None:
        result = await db_session.execute(select(Vault).where(Vault.id == vault_id))
        return result.scalar_one_or_none()


pvp_duel = CRUDPvpDuel(PvpDuel)
