"""Weapon-specific queries; compatible with raw SQLAlchemy task sessions."""

from datetime import datetime, timedelta

from pydantic import UUID4
from sqlalchemy import func, update
from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.item_base import CRUDItem
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.schemas.weapon import WeaponCreate, WeaponUpdate


class CRUDWeapon(CRUDItem[Weapon, WeaponCreate, WeaponUpdate]):
    async def list_due_for_trial(
        self, db: AsyncSession, storage_id: UUID4, cutoff: datetime, names: tuple[str, ...]
    ) -> list[Weapon]:
        result = await db.execute(
            select(Weapon)
            .where(
                Weapon.storage_id == storage_id,
                col(Weapon.dweller_id).is_(None),
                col(Weapon.exploration_id).is_(None),
                func.lower(func.trim(Weapon.name)).in_(names),
                or_(col(Weapon.last_maintenance_trial_at).is_(None), col(Weapon.last_maintenance_trial_at) <= cutoff),
            )
            .order_by(col(Weapon.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def advance_trial_clock(self, db: AsyncSession, ids: list[UUID4], now: datetime) -> None:
        """Consume locked offline trials without rolling or loading workers."""
        if ids:
            await db.execute(update(Weapon).where(col(Weapon.id).in_(ids)).values(last_maintenance_trial_at=now))

    async def shift_trial_clocks(self, db: AsyncSession, vault_id: UUID4, paused: timedelta, now: datetime) -> None:
        result = await db.execute(
            select(Weapon)
            .join(Storage)
            .where(Storage.vault_id == vault_id, col(Weapon.last_maintenance_trial_at).is_not(None))
            .with_for_update()
        )
        for weapon in result.scalars():
            weapon.last_maintenance_trial_at = min(weapon.last_maintenance_trial_at + paused, now)
            db.add(weapon)


weapon = CRUDWeapon(Weapon)
