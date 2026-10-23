"""Adoption service and family-tick adoption tests."""

from typing import Any

import pytest
from sqlmodel import select

from app import crud
from app.core.enums import AgeGroupEnum, RelationshipTypeEnum
from app.crud.relationship import relationship_crud
from app.models.notification import Notification, NotificationType
from app.schemas.user import UserCreate
from app.services.family.adoption_service import adoption_service
from app.services.game_tick import family_tick
from app.services.notification_service import notification_service
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
    first = await _dweller(async_session, vault_id)
    second = await _dweller(async_session, vault_id)
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

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("notification failed")

    monkeypatch.setattr(notification_service, "create_and_send", _boom)

    with pytest.raises(RuntimeError):
        await adoption_service.process_adoptions(async_session, vault.id)
    await async_session.rollback()
    await async_session.refresh(child)
    assert child.parent_1_id == original_parent_id
