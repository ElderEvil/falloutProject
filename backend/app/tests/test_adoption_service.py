"""Adoption service and family-tick adoption tests."""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RaceEnum, RelationshipTypeEnum
from app.crud.relationship import relationship_crud
from app.models.notification import Notification, NotificationType
from app.schemas.user import UserCreate
from app.services.family.adoption_service import adoption_service
from app.services.game_loop import game_loop_service
from app.services.game_tick import family_tick
from app.services.notification_service import notification_service
from app.services.stream_manager import sse_manager
from app.tests.factory.dwellers import create_random_common_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import random_vault_number

pytestmark = pytest.mark.asyncio


async def _vault(async_session) -> Any:
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": random_vault_number()},
        user_id=user.id,
    )


async def _dweller(async_session, vault_id, **overrides):
    data = create_random_common_dweller() | {"vault_id": vault_id} | overrides
    return await crud.dweller.create(db_session=async_session, obj_in=data)


async def _couple(async_session, vault_id, relationship_type=RelationshipTypeEnum.PARTNER):
    first = await _dweller(async_session, vault_id, gender=GenderEnum.FEMALE)
    second = await _dweller(async_session, vault_id, gender=GenderEnum.MALE)
    first.partner_id = second.id
    second.partner_id = first.id
    async_session.add(first)
    async_session.add(second)
    await async_session.commit()
    await relationship_crud.create(
        db_session=async_session,
        obj_in={
            "dweller_1_id": first.id,
            "dweller_2_id": second.id,
            "relationship_type": relationship_type,
        },
    )
    return first, second


async def _orphan(async_session, vault_id, parent_alive: bool = False):
    parent = await _dweller(async_session, vault_id)
    if not parent_alive:
        parent.is_dead = True
        async_session.add(parent)
        await async_session.commit()
    child = await _dweller(async_session, vault_id, age_group=AgeGroupEnum.CHILD)
    child.parent_1_id = parent.id
    async_session.add(child)
    await async_session.commit()
    await async_session.refresh(child)
    return child


async def test_orphan_is_adopted_by_committed_couple(async_session):
    vault = await _vault(async_session)
    first_parent, second_parent = await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)

    adopted = await adoption_service.process_adoptions(async_session, vault.id)

    await async_session.refresh(child)
    assert len(adopted) == 1
    assert child.parent_1_id == first_parent.id
    assert child.parent_2_id == second_parent.id
    notifications = (
        await async_session.exec(
            select(Notification).where(Notification.notification_type == NotificationType.CHILD_ADOPTED)
        )
    ).all()
    assert len(notifications) == 1


async def test_child_with_living_parent_is_not_adopted(async_session):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id, parent_alive=True)

    adopted = await adoption_service.process_adoptions(async_session, vault.id)

    await async_session.refresh(child)
    assert adopted == []
    assert child.parent_1_id is not None


async def test_no_committed_couple_means_no_adoption(async_session):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id, relationship_type=RelationshipTypeEnum.FRIEND)
    child = await _orphan(async_session, vault.id)
    original_parent_id = child.parent_1_id

    adopted = await adoption_service.process_adoptions(async_session, vault.id)

    await async_session.refresh(child)
    assert adopted == []
    assert child.parent_1_id == original_parent_id


async def test_family_tick_reports_adoptions(async_session):
    class _StubService:
        async def _update_room_relationships(self, *_args, **_kwargs):
            return {"relationships_updated": 0}

        async def _process_pregnancies_and_births(self, *_args, **_kwargs):
            return {"conceptions": 0, "births": 0}

        async def _age_children(self, *_args, **_kwargs):
            return {"children_aged": 0}

    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    await _orphan(async_session, vault.id)

    stats = await family_tick.process_breeding(_StubService(), async_session, vault.id)

    assert stats["adoptions"] == 1


async def test_dead_child_is_not_adopted(async_session):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    child.is_dead = True
    async_session.add(child)
    await async_session.commit()

    adopted = await adoption_service.process_adoptions(async_session, vault.id)

    assert adopted == []


async def test_second_run_is_a_noop(async_session):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)

    first = await adoption_service.process_adoptions(async_session, vault.id)
    second = await adoption_service.process_adoptions(async_session, vault.id)

    assert len(first) == 1
    assert second == []
    await async_session.refresh(child)
    assert child.parent_1_id is not None


async def test_child_and_both_adopters_get_bio_entries(async_session):
    vault = await _vault(async_session)
    first_parent, second_parent = await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)

    await adoption_service.process_adoptions(async_session, vault.id)

    await async_session.refresh(child)
    await async_session.refresh(first_parent)
    await async_session.refresh(second_parent)
    entry = next(e for e in child.bio_entries if e.get("ref", {}).get("adopted") is True)
    assert entry["ref"]["adopter_1_id"] in {str(first_parent.id), str(second_parent.id)}
    for parent in (first_parent, second_parent):
        assert any(e.get("ref", {}).get("child_id") == str(child.id) for e in parent.bio_entries)


async def test_failed_notification_rolls_back_adoption(async_session, monkeypatch):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    original_parent_id = child.parent_1_id

    def fail_insert(*_args):
        raise RuntimeError("notification failed")

    event.listen(Notification, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="notification failed"):
            await adoption_service.process_adoptions(async_session, vault.id)
    finally:
        event.remove(Notification, "before_insert", fail_insert)
    await async_session.rollback()
    await async_session.refresh(child)
    assert child.parent_1_id == original_parent_id


@pytest.mark.parametrize("missing", [False, True])
async def test_deleted_or_missing_parent_does_not_abort_adoption(async_session, missing):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    if missing:
        child.parent_1_id = uuid4()
        async_session.add(child)
    else:
        parent = await crud.dweller.get(async_session, child.parent_1_id)
        parent.is_deleted = True
        async_session.add(parent)
    await async_session.commit()

    adopted = await adoption_service.process_adoptions(async_session, vault.id)
    assert [dweller.id for dweller in adopted] == [child.id]


async def test_deleted_parent_with_living_other_parent_is_skipped(async_session):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    parent = await crud.dweller.get(async_session, child.parent_1_id)
    parent.is_deleted = True
    living_parent = await _dweller(async_session, vault.id)
    child.parent_2_id = living_parent.id
    async_session.add_all([parent, child])
    await async_session.commit()
    assert await adoption_service.process_adoptions(async_session, vault.id) == []


@pytest.mark.parametrize("race", [RaceEnum.HUMAN, RaceEnum.GHOUL])
async def test_same_gender_couple_uses_stable_parent_order(async_session, race):
    vault = await _vault(async_session)
    first, second = await _couple(async_session, vault.id)
    first.gender = second.gender = GenderEnum.MALE
    second.visual_attributes = {**(second.visual_attributes or {}), "race": race.value}
    async_session.add_all([first, second])
    await async_session.commit()
    child = await _orphan(async_session, vault.id)
    await adoption_service.process_adoptions(async_session, vault.id)
    assert (child.parent_1_id, child.parent_2_id) == tuple(sorted([first.id, second.id], key=str))


async def test_raw_session_adoption_commits_before_delivery(async_session, monkeypatch):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    child_id, vault_id = child.id, vault.id
    delivered = []

    async with RawAsyncSession(
        bind=async_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as raw:
        assert not hasattr(raw, "exec")

        from app.services.notification_service import manager, sse_manager

        async def publish(user_id, stream, payload):
            assert not raw.in_transaction()
            delivered.append(payload)

        monkeypatch.setattr(sse_manager, "publish", publish)
        monkeypatch.setattr(manager, "send_personal_message", AsyncMock())
        adopted = await adoption_service.process_adoptions(raw, vault_id)
        assert [dweller.id for dweller in adopted] == [child_id]
        assert len(delivered) == 1
        assert delivered[0]["notification"]["notification_type"] == NotificationType.CHILD_ADOPTED
        assert "deferred_notification_deliveries" not in raw.info
        assert await adoption_service.process_adoptions(raw, vault_id) == []


async def test_duplicate_relationship_rows_do_not_reuse_a_couple(async_session):
    vault = await _vault(async_session)
    first, second = await _couple(async_session, vault.id)
    await relationship_crud.create(
        db_session=async_session,
        obj_in={
            "dweller_1_id": second.id,
            "dweller_2_id": first.id,
            "relationship_type": RelationshipTypeEnum.PARTNER,
        },
    )
    await _orphan(async_session, vault.id)
    await _orphan(async_session, vault.id)
    assert len(await adoption_service.process_adoptions(async_session, vault.id)) == 1


async def test_adoption_lookup_failure_does_not_abort_later_tick_phases(async_session, vault, monkeypatch):
    vault_id = vault.id
    publish = AsyncMock()
    monkeypatch.setattr(sse_manager, "publish", publish)
    connection = await async_session.connection()
    failed = False
    rollbacks = []

    def fail_lookup(_conn, _cursor, statement, parameters, _context, _executemany):
        nonlocal failed
        if not failed and "dweller.parent_1_id IS NOT NULL" in statement:
            failed = True
            raise OperationalError(statement, parameters, RuntimeError("adoption lookup unavailable"))

    def record_rollback(_session):
        rollbacks.append(True)

    event.listen(connection.sync_connection, "before_cursor_execute", fail_lookup)
    event.listen(async_session.sync_session, "after_rollback", record_rollback)
    try:
        result = await game_loop_service.process_vault_tick(async_session, vault_id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", fail_lookup)
        event.remove(async_session.sync_session, "after_rollback", record_rollback)

    assert failed
    assert rollbacks
    assert result["updates"]["breeding"] == {
        "relationships_updated": 0,
        "conceptions": 0,
        "births": 0,
        "children_aged": 0,
        "adoptions": 0,
    }
    assert "arena" in result["updates"]
    assert "events" in result["updates"]
    assert any(call.args[1] == "game_ticks" for call in publish.call_args_list)
