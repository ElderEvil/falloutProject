"""Perk selection persists eligibility and progression as one operation."""

import asyncio
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import AgeGroupEnum, DwellerPerk, DwellerStatusEnum, NotificationType
from app.models.notification import Notification
from app.options.identity_modifiers import effective_stat
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.catalog_service import load_outfits
from app.services.notification_service import manager, sse_manager
from app.services.perk_service import perk_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import AccessDeniedException, ResourceConflictException, ValidationException
from app.utils.item_factory import build_outfit


async def _eligible(session, dweller):
    dweller.level = 5
    dweller.intelligence = 4
    dweller.charisma = 6
    dweller.age_group = AgeGroupEnum.ADULT
    dweller.is_dead = False
    dweller.status = DwellerStatusEnum.IDLE
    session.add(dweller)
    await session.commit()


@pytest.fixture
def transport(monkeypatch):
    websocket, sse = AsyncMock(), AsyncMock()
    monkeypatch.setattr(manager, "send_personal_message", websocket)
    monkeypatch.setattr(sse_manager, "publish", sse)
    return websocket, sse


async def test_selection_persists_one_perk_and_notification(async_session, dweller, vault, transport):
    await _eligible(async_session, dweller)
    selected = await perk_service.select(async_session, dweller.id, DwellerPerk.HACKER, vault.user_id)
    await async_session.refresh(dweller)
    assert dweller.selected_perk == selected.selected_perk == DwellerPerk.HACKER
    assert not any(option.eligible for option in selected.options)
    notifications = (
        await async_session.exec(
            select(Notification).where(
                Notification.from_dweller_id == dweller.id,
                Notification.notification_type == NotificationType.PERK_UNLOCKED,
            )
        )
    ).all()
    assert len(notifications) == 1
    assert transport[0].await_count == transport[1].await_count == 1
    with pytest.raises(ResourceConflictException):
        await perk_service.select(async_session, dweller.id, DwellerPerk.TERRIFYING_PRESENCE, vault.user_id)
    await async_session.rollback()
    assert transport[0].await_count == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("level", 4),
        ("intelligence", 3),
        ("is_dead", True),
        ("age_group", AgeGroupEnum.TEEN),
        ("status", DwellerStatusEnum.EXPLORING),
    ],
)
async def test_ineligible_selection_preserves_empty_slot(async_session, dweller, vault, field, value, transport):
    await _eligible(async_session, dweller)
    setattr(dweller, field, value)
    await async_session.commit()
    dweller_id = dweller.id
    with pytest.raises(ValidationException):
        await perk_service.select(async_session, dweller_id, DwellerPerk.HACKER, vault.user_id)
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert dweller.selected_perk is None
    assert transport[0].await_count == transport[1].await_count == 0


async def test_selection_rechecks_current_owner(async_session, dweller, transport):
    await _eligible(async_session, dweller)
    with pytest.raises(AccessDeniedException):
        await perk_service.select(async_session, dweller.id, DwellerPerk.HACKER, uuid4())
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert dweller.selected_perk is None
    assert transport[0].await_count == 0


async def test_equipped_intelligence_cannot_grant_learning_eligibility(async_session, dweller, vault, transport):
    await _eligible(async_session, dweller)
    dweller.intelligence = 3
    data = next(outfit for outfit in load_outfits() if outfit.get("intelligence", 0) > 0)
    outfit = build_outfit(data, data["rarity"])
    outfit.dweller_id = dweller.id
    async_session.add(outfit)
    await async_session.commit()
    equipped = await crud.dweller.get(async_session, dweller.id)
    assert effective_stat(equipped, "intelligence") >= 4
    with pytest.raises(ValidationException, match="trained intelligence"):
        await perk_service.select(async_session, dweller.id, DwellerPerk.HACKER, vault.user_id)
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert dweller.selected_perk is None
    assert transport[0].await_count == 0


async def test_late_notification_failure_rolls_back_selection(async_session, dweller, vault, transport):
    await _eligible(async_session, dweller)
    dweller_id, owner_id = dweller.id, vault.user_id
    connection = (await async_session.connection()).sync_connection

    def fail_notification(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO notification"):
            raise RuntimeError("late notification write failed")

    event.listen(connection, "before_cursor_execute", fail_notification)
    try:
        with pytest.raises(RuntimeError, match="late notification"):
            await perk_service.select(async_session, dweller_id, DwellerPerk.HACKER, owner_id)
    finally:
        event.remove(connection, "before_cursor_execute", fail_notification)
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert dweller.selected_perk is None
    assert not (await async_session.exec(select(Notification).where(Notification.from_dweller_id == dweller_id))).all()
    assert transport[0].await_count == transport[1].await_count == 0
    assert "deferred_notification_deliveries" not in async_session.info


@pytest.mark.integration
async def test_concurrent_perk_selection_has_one_winner(transport):
    if os.getenv("PERK_POSTGRES_TESTS") != "1" or not settings.POSTGRES_DB.startswith("fallout_perks_1316_"):
        pytest.skip("Requires an isolated, migrated perk-test PostgreSQL database.")
    engine = create_async_engine(str(settings.ASYNC_DATABASE_URI), poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = await crud.user.create(db, obj_in=UserCreate(**create_fake_user()))
            vault = await crud.vault.create(db, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
            dweller = await crud.dweller.create(
                db,
                obj_in=DwellerCreate(
                    **(create_fake_adult_dweller() | {"level": 5, "intelligence": 4, "charisma": 6}),
                    vault_id=vault.id,
                ),
            )
            await _eligible(db, dweller)
            dweller_id, user_id = dweller.id, user.id

        async def choose(perk):
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    return await perk_service.select(db, dweller_id, perk, user_id)
                except ResourceConflictException:
                    await db.rollback()
                    return None

        results = await asyncio.gather(choose(DwellerPerk.HACKER), choose(DwellerPerk.TERRIFYING_PRESENCE))
        assert sum(result is not None for result in results) == 1
        async with AsyncSession(engine) as db:
            saved = await crud.dweller.get(db, dweller_id)
            winner = next(result for result in results if result is not None)
            assert saved.selected_perk == winner.selected_perk
            notices = (await db.exec(select(Notification).where(Notification.from_dweller_id == dweller_id))).all()
            assert len(notices) == 1
        assert transport[0].await_count == transport[1].await_count == 1
    finally:
        await engine.dispose()
