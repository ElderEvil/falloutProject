from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, NotificationType, RaceEnum, RelationshipTypeEnum
from app.core.game_config import game_config
from app.core.stream_manager import sse_manager
from app.crud.relationship import relationship_crud
from app.models.notification import Notification
from app.schemas.user import UserCreate
from app.services.family.adoption_service import adoption_service
from app.services.game_loop_service import game_loop_service
from app.services.game_tick import family_tick
from app.services.notification_service import manager, notification_service
from app.tests.factory.dwellers import create_random_common_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import random_vault_number
from app.utils.time import utcnow


@pytest.fixture(autouse=True)
def successful_adoption_roll(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.0)


async def _vault(async_session) -> Any:
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create_with_user_id(
        db_session=async_session, obj_in={"number": random_vault_number()}, user_id=user.id
    )


async def _dweller(async_session, vault_id, **overrides):
    data = create_random_common_dweller() | {"vault_id": vault_id} | overrides
    return await crud.dweller.create(db_session=async_session, obj_in=data)


async def _couple(async_session, vault_id, relationship_type=RelationshipTypeEnum.PARTNER):
    first = await _dweller(async_session, vault_id, gender=GenderEnum.FEMALE, happiness=80)
    second = await _dweller(async_session, vault_id, gender=GenderEnum.MALE, happiness=80)
    first.partner_id = second.id
    second.partner_id = first.id
    async_session.add_all([first, second])
    await async_session.commit()
    await relationship_crud.create(
        db_session=async_session,
        obj_in={
            "dweller_1_id": first.id,
            "dweller_2_id": second.id,
            "relationship_type": relationship_type,
            "affinity": game_config.relationship.marriage_threshold,
        },
    )
    return first, second


async def _orphan(async_session, vault_id, parent_alive: bool = False):
    parent = await _dweller(async_session, vault_id)
    if not parent_alive:
        parent.is_dead = True
        async_session.add(parent)
        await async_session.commit()
    child = await _dweller(async_session, vault_id, age_group=AgeGroupEnum.CHILD, birth_date=utcnow())
    child.parent_1_id = parent.id
    async_session.add(child)
    await async_session.commit()
    await async_session.refresh(child)
    return child


async def _family(async_session, relationship_type=RelationshipTypeEnum.PARTNER, parent_alive=False):
    vault = await _vault(async_session)
    parents = await _couple(async_session, vault.id, relationship_type)
    child = await _orphan(async_session, vault.id, parent_alive=parent_alive)
    return vault, parents, child


async def _adopt(async_session, vault_id, seconds_passed=60):
    return await adoption_service.process_adoptions(async_session, vault_id, seconds_passed=seconds_passed)


async def test_orphan_is_adopted_by_committed_couple(async_session):
    vault, (first_parent, second_parent), child = await _family(async_session)
    adopted = await _adopt(async_session, vault.id)
    await async_session.refresh(child)
    assert ((len(adopted), child.parent_1_id), child.parent_2_id) == ((1, first_parent.id), second_parent.id)
    notifications = (
        await async_session.exec(
            select(Notification).where(Notification.notification_type == NotificationType.RELATIONSHIP_FORMED)
        )
    ).all()
    assert (len(notifications), notifications[0].meta_data["event"]) == (1, "child_adopted")
    await async_session.refresh(first_parent)
    await async_session.refresh(second_parent)
    entry = next(e for e in child.bio_entries if e.get("ref", {}).get("adopted") is True)
    assert entry["ref"]["adopter_1_id"] in {str(first_parent.id), str(second_parent.id)}
    for parent in (first_parent, second_parent):
        assert any(e.get("ref", {}).get("child_id") == str(child.id) for e in parent.bio_entries)
    assert await _adopt(async_session, vault.id) == []
    await async_session.refresh(child)
    assert child.parent_1_id is not None


async def test_family_tick_reports_adoptions(async_session):
    class _StubService:
        async def _update_room_relationships(self, *_args, **_kwargs):
            return {"relationships_updated": 0}

        async def _process_pregnancies_and_births(self, *_args, **_kwargs):
            return {"conceptions": 0, "births": 0}

        async def _age_children(self, *_args, **_kwargs):
            return {"children_aged": 0}

    vault, _, _ = await _family(async_session)
    stats = await family_tick.process_breeding(_StubService(), async_session, vault.id, seconds_passed=60)
    assert stats["adoptions"] == 1


async def test_failed_notification_rolls_back_adoption(async_session):
    vault, _, child = await _family(async_session)
    original_parent_id = child.parent_1_id

    def fail_insert(*_args):
        raise RuntimeError("notification failed")

    event.listen(Notification, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="notification failed"):
            await _adopt(async_session, vault.id)
    finally:
        event.remove(Notification, "before_insert", fail_insert)
    await async_session.rollback()
    await async_session.refresh(child)
    assert child.parent_1_id == original_parent_id


@pytest.mark.parametrize("case", ["missing", "deleted", "deleted_other_living"])
async def test_parent_state_does_not_abort_adoption(async_session, case: str) -> None:
    vault, _, child = await _family(async_session)
    if case == "missing":
        child.parent_1_id = uuid4()
        async_session.add(child)
    else:
        parent = await crud.dweller.get(async_session, child.parent_1_id)
        parent.is_deleted = True
        async_session.add(parent)
        if case == "deleted_other_living":
            child.parent_2_id = (await _dweller(async_session, vault.id)).id
            async_session.add(child)
    await async_session.commit()
    adopted = await _adopt(async_session, vault.id)
    assert [dweller.id for dweller in adopted] == ([] if case == "deleted_other_living" else [child.id])


@pytest.mark.parametrize("race", [RaceEnum.HUMAN, RaceEnum.GHOUL])
async def test_same_gender_couple_uses_stable_parent_order(async_session, race):
    vault, (first, second), child = await _family(async_session)
    first.gender = second.gender = GenderEnum.MALE
    second.visual_attributes = {**(second.visual_attributes or {}), "race": race.value}
    async_session.add_all([first, second])
    await async_session.commit()
    await _adopt(async_session, vault.id)
    assert (child.parent_1_id, child.parent_2_id) == tuple(sorted([first.id, second.id], key=str))


async def test_raw_session_adoption_commits_before_delivery(async_session, monkeypatch):
    vault, _, child = await _family(async_session)
    child_id, vault_id = child.id, vault.id
    delivered = []
    async with RawAsyncSession(
        bind=async_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as raw:
        assert not hasattr(raw, "exec")

        async def publish(user_id, stream, payload):
            assert not raw.in_transaction()
            delivered.append(payload)

        monkeypatch.setattr(sse_manager, "publish", publish)
        monkeypatch.setattr(manager, "send_personal_message", AsyncMock())
        adopted = await _adopt(raw, vault_id)
        assert ([dweller.id for dweller in adopted], len(delivered)) == ([child_id], 1)
        assert delivered[0]["notification"]["notification_type"] == NotificationType.RELATIONSHIP_FORMED
        assert "deferred_notification_deliveries" not in raw.info
        assert await _adopt(raw, vault_id) == []


async def test_duplicate_relationship_rows_do_not_reuse_a_couple(async_session):
    vault, (first, second), _ = await _family(async_session)
    await relationship_crud.create(
        db_session=async_session,
        obj_in={
            "dweller_1_id": second.id,
            "dweller_2_id": first.id,
            "relationship_type": RelationshipTypeEnum.PARTNER,
            "affinity": game_config.relationship.marriage_threshold,
        },
    )
    await _orphan(async_session, vault.id)
    await _orphan(async_session, vault.id)
    assert len(await _adopt(async_session, vault.id)) == 1


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


@pytest.mark.parametrize("blocked", ["living_parent", "friend", "dead_child", "unhappy", "low_affinity", "full_family"])
async def test_ineligible_family_does_not_adopt(async_session, blocked):
    relationship_type = RelationshipTypeEnum.FRIEND if blocked == "friend" else RelationshipTypeEnum.PARTNER
    vault, (first, second), child = await _family(
        async_session, relationship_type, parent_alive=blocked == "living_parent"
    )
    original_parent_id = child.parent_1_id
    if blocked == "dead_child":
        child.is_dead = True
        async_session.add(child)
    elif blocked == "unhappy":
        first.happiness = 59
        async_session.add(first)
    elif blocked == "low_affinity":
        relationship = await relationship_crud.get_by_dweller_pair(async_session, first.id, second.id)
        relationship.affinity = game_config.relationship.marriage_threshold - 1
        async_session.add(relationship)
    elif blocked == "full_family":
        for age in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN):
            await _dweller(async_session, vault.id, age_group=age, parent_1_id=first.id, parent_2_id=second.id)
    await async_session.commit()
    assert await _adopt(async_session, vault.id) == []
    await async_session.refresh(child)
    assert child.parent_1_id == original_parent_id
    assert child.parent_2_id is None


@pytest.mark.parametrize(
    ("seconds", "chance_per_hour", "roll", "adopts"),
    [(60, None, 0.01, False), (3600, None, 0.01, True), (1800, 0.64, 0.39, True)],
)
async def test_adoption_chance_scales_with_elapsed_time(
    async_session, monkeypatch, seconds: int, chance_per_hour: float | None, roll: float, adopts: bool
) -> None:
    vault, _, child = await _family(async_session)
    if chance_per_hour is not None:
        # 64% over an hour means 40% over each half hour, not 32%.
        monkeypatch.setattr(game_config.breeding, "adoption_chance_per_hour", chance_per_hour)
    monkeypatch.setattr("random.random", lambda: roll)
    adopted = await _adopt(async_session, vault.id, seconds_passed=seconds)
    assert [dweller.id for dweller in adopted] == ([child.id] if adopts else [])


async def test_failed_roll_changes_nothing_even_with_multiple_couples(async_session, monkeypatch):
    vault = await _vault(async_session)
    await _couple(async_session, vault.id)
    await _couple(async_session, vault.id)
    child = await _orphan(async_session, vault.id)
    original_parent_id = child.parent_1_id
    rolls = []

    def miss():
        rolls.append(True)
        return 1.0

    monkeypatch.setattr("random.random", miss)
    assert (await _adopt(async_session, vault.id, seconds_passed=3600), len(rolls)) == ([], 1)
    await async_session.refresh(child)
    assert child.parent_1_id == original_parent_id
    assert child.parent_2_id is None
    assert not any(entry.get("ref", {}).get("adopted") for entry in child.bio_entries or [])
    assert (await async_session.execute(select(Notification))).scalars().all() == []


async def test_manual_breeding_call_does_not_roll_adoption(async_session):
    vault, _, child = await _family(async_session)
    stats = await game_loop_service.process_vault_breeding(async_session, vault.id)
    assert stats["adoptions"] == 0
    await async_session.refresh(child)
    assert child.age_group == AgeGroupEnum.CHILD
    assert child.parent_2_id is None


async def test_adult_and_dead_children_do_not_fill_family_slots(async_session):
    vault, (first, second), child = await _family(async_session)
    await _dweller(async_session, vault.id, parent_1_id=first.id, parent_2_id=second.id, age_group=AgeGroupEnum.ADULT)
    await _dweller(
        async_session, vault.id, parent_1_id=first.id, parent_2_id=second.id, age_group=AgeGroupEnum.CHILD, is_dead=True
    )
    adopted = await _adopt(async_session, vault.id)
    assert [dweller.id for dweller in adopted] == [child.id]


async def test_later_adoptions_stop_when_family_reaches_capacity(async_session):
    vault, _, _ = await _family(async_session)
    for _ in range(3):
        await _orphan(async_session, vault.id)
    first = await _adopt(async_session, vault.id)
    second = await _adopt(async_session, vault.id)
    third = await _adopt(async_session, vault.id)
    assert len(first) == len(second) == 1
    assert first[0].id != second[0].id
    assert third == []
