import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.enums import NotificationType, PvpDuelStatus
from app.crud import pvp_duel as pvp_duel_crud
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.services.pvp_duel_service import pvp_duel_service

pytest_plugins = ["app.tests.test_alembic._support"]
from app.tests.test_db.test_collectible_award_concurrency import vault_with_dweller
from app.utils.exceptions import DomainError

COMBAT_TYPES = [NotificationType.COMBAT_VICTORY, NotificationType.COMBAT_DEFEAT]


@pytest.mark.integration
async def test_two_simultaneous_accepts_settle_once(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db:
        challenger_user, challenger_vault, challenger_dweller = await vault_with_dweller(
            db, prefix="pvp", surname="Tester", password="duelpw123"
        )
        _, defender_vault, defender_dweller = await vault_with_dweller(
            db, prefix="pvp", surname="Tester", password="duelpw123"
        )
        posted = await pvp_duel_service.post(db, challenger_vault.id, dweller_ids=[challenger_dweller.id])

    async def _accept() -> object:
        async with maker() as session:
            try:
                return await pvp_duel_service.accept(
                    session, defender_vault.id, posted.duel_id, dweller_ids=[defender_dweller.id]
                )
            except DomainError as exc:
                return exc

    first, second = await asyncio.gather(_accept(), _accept())
    results = [first, second]
    assert sum(not isinstance(result, DomainError) for result in results) == 1
    async with maker() as db:
        duel = await pvp_duel_crud.get_duel(db, posted.duel_id)
        assert duel is not None
        assert PvpDuelStatus(duel.status) == PvpDuelStatus.ACCEPTED
        assert duel.journal
        count = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == challenger_user.id,
                Notification.notification_type.in_(COMBAT_TYPES),
            )
        )
        assert count.scalar_one() == 1
        await db.delete(duel)
        for vault_id in (challenger_vault.id, defender_vault.id):
            dwellers = await db.execute(select(Dweller).where(Dweller.vault_id == vault_id))
            for dweller in dwellers.scalars().all():
                await db.delete(dweller)
        await db.commit()
