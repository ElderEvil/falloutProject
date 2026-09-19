"""Tests for quest availability unification (read/start agreement + Office rule)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.room import Room
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.quest_service import quest_service
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


async def _vault_with_office(async_session: AsyncSession):
    """A vault that has built the Overseer's Office."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    await async_session.commit()
    return vault


async def _create_quest(async_session: AsyncSession, *, title: str, previous_quest_id=None) -> Quest:
    quest = Quest(
        title=title,
        short_description="Test quest",
        long_description="A quest used to exercise availability.",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
        previous_quest_id=previous_quest_id,
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)
    return quest


@pytest.mark.asyncio
async def test_requirement_gated_quest_reads_as_locked_and_start_rejects(
    async_client, async_session: AsyncSession
) -> None:
    """A quest with an unmet mandatory DWELLER_COUNT requirement must not read as available and must not start."""
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    quest = Quest(
        title="Population Gate",
        short_description="Needs 100 dwellers",
        long_description="A quest gated on vault population.",
        requirements="100 dwellers",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.DWELLER_COUNT,
            requirement_data={"count": 100},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    read_response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert read_response.status_code == 200, f"Expected 200, got {read_response.status_code}: {read_response.text}"
    quest_read = next(q for q in read_response.json() if q["id"] == str(quest.id))
    assert quest_read["is_locked"] is True
    assert quest_read["is_visible"] is False
    assert "dwellers" in quest_read["lock_reason"]

    start_response = await async_client.post(f"/quests/{vault.id}/{quest.id}/start", headers=headers)
    assert start_response.status_code == 400, f"Expected 400, got {start_response.status_code}: {start_response.text}"
    assert "dwellers" in start_response.json()["detail"]


@pytest.mark.asyncio
async def test_quest_is_locked_without_overseers_office(async_session: AsyncSession) -> None:
    """All quests are locked until the vault builds the Overseer's Office."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await _create_quest(async_session, title="Office Gate")

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest)

    assert availability.available is False
    assert availability.lock_reason == "Requires Overseer's Office"
    assert availability.missing == []


@pytest.mark.asyncio
async def test_requirement_gated_quest_lock_reason(async_session: AsyncSession) -> None:
    """An unmet mandatory requirement surfaces as the lock reason."""
    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Dweller Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.DWELLER_COUNT,
            requirement_data={"count": 100},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest)

    assert availability.available is False
    assert "dwellers" in availability.lock_reason
    assert any("dwellers" in missing for missing in availability.missing)


@pytest.mark.asyncio
async def test_chain_locked_quest(async_session: AsyncSession) -> None:
    """A quest whose chain predecessor is incomplete is locked until it completes."""
    vault = await _vault_with_office(async_session)
    quest_a = await _create_quest(async_session, title="Chain Starter")
    quest_b = await _create_quest(async_session, title="Chain Follow-up", previous_quest_id=quest_a.id)

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest_b)
    assert availability.available is False
    assert availability.lock_reason == "Requires completing a previous quest"

    await crud.quest_crud.assign_to_vault(async_session, quest_a.id, vault.id, is_visible=True)
    link = await crud.quest_crud.get_link(async_session, quest_id=quest_a.id, vault_id=vault.id)
    link.is_completed = True
    await async_session.commit()

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest_b)
    assert availability.available is True
    assert availability.lock_reason is None


@pytest.mark.asyncio
async def test_fully_available_quest(async_session: AsyncSession) -> None:
    """A quest with the office, no chain, and no requirements is available."""
    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Open Quest")

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest)

    assert availability.available is True
    assert availability.lock_reason is None
    assert availability.missing == []


@pytest.mark.asyncio
async def test_get_quests_for_vault_populates_lock_fields(async_session: AsyncSession) -> None:
    """The vault quest read reports is_locked/lock_reason from the shared function."""
    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Read Path Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.DWELLER_COUNT,
            requirement_data={"count": 100},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is True
    assert quest_read.is_visible is False
    assert "dwellers" in quest_read.lock_reason
