"""Tests for the reusable team roster assignment service."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import AgeGroupEnum
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.quest_service import quest_service
from app.services.team_service import team_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException


async def _make_quest_vault(async_session: AsyncSession, *, title: str = "Team Quest") -> tuple[Vault, Quest]:
    """A vault with a quest assigned and visible."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title=title,
            short_description="Send a team",
            long_description="A quest that needs a team roster.",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=60,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    return vault, quest


async def _make_adult_dweller(async_session: AsyncSession, vault: Vault) -> Dweller:
    data = create_fake_dweller()
    data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest.mark.asyncio
async def test_assign_quest_team_assigns_dwellers(async_session: AsyncSession) -> None:
    """Assigning a team marks members QUESTING with sequential slots."""
    vault, quest = await _make_quest_vault(async_session)
    dweller1 = await _make_adult_dweller(async_session, vault)
    dweller2 = await _make_adult_dweller(async_session, vault)

    members = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller1.id, dweller2.id])

    assert [member.dweller_id for member in members] == [dweller1.id, dweller2.id]
    assert [member.slot_number for member in members] == [1, 2]
    assert all(member.status == "assigned" for member in members)
    await async_session.refresh(dweller1)
    await async_session.refresh(dweller2)
    assert dweller1.status == DwellerStatusEnum.QUESTING
    assert dweller2.status == DwellerStatusEnum.QUESTING


@pytest.mark.asyncio
async def test_assign_quest_team_replaces_existing(async_session: AsyncSession) -> None:
    """Reassigning a team frees the old dwellers back to IDLE."""
    vault, quest = await _make_quest_vault(async_session)
    dweller1 = await _make_adult_dweller(async_session, vault)
    dweller2 = await _make_adult_dweller(async_session, vault)

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller1.id])
    members = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller2.id])

    assert [member.dweller_id for member in members] == [dweller2.id]
    await async_session.refresh(dweller1)
    await async_session.refresh(dweller2)
    assert dweller1.status == DwellerStatusEnum.IDLE
    assert dweller2.status == DwellerStatusEnum.QUESTING


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, 4])
async def test_assign_quest_team_size_limits(async_session: AsyncSession, size: int) -> None:
    """Teams hold 1-3 dwellers."""
    vault, quest = await _make_quest_vault(async_session)
    dwellers = [await _make_adult_dweller(async_session, vault) for _ in range(4)]

    with pytest.raises(ValidationException, match="Party size must be 1-3"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [d.id for d in dwellers[:size]])


@pytest.mark.asyncio
async def test_assign_quest_team_rejects_duplicate_dwellers(async_session: AsyncSession) -> None:
    """A dweller listed twice is rejected before the size check, never double-slotted."""
    vault, quest = await _make_quest_vault(async_session)
    dweller = await _make_adult_dweller(async_session, vault)

    with pytest.raises(ValidationException, match="only once"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id, dweller.id])

    assert await crud.team_crud.get_quest_team(async_session, quest.id, vault.id) == []


@pytest.mark.asyncio
async def test_get_quest_team_orders_members_by_slot(async_session: AsyncSession) -> None:
    """get_quest_team returns members slot-ordered, missing slots first."""
    vault, quest = await _make_quest_vault(async_session)
    dwellers = [await _make_adult_dweller(async_session, vault) for _ in range(3)]
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [d.id for d in dwellers])

    # Scramble slot numbers and add a slot-less member to pin the ordering contract.
    team = await crud.team_crud.get_quest_team_row(async_session, quest.id, vault.id)
    assert team is not None
    for member in team.members:
        member.slot_number = None
    await async_session.commit()
    by_dweller = {member.dweller_id: member for member in team.members}
    by_dweller[dwellers[0].id].slot_number = 3
    by_dweller[dwellers[2].id].slot_number = 1
    await async_session.commit()

    members = await crud.team_crud.get_quest_team(async_session, quest.id, vault.id)
    assert [member.slot_number for member in members] == [None, 1, 3]


@pytest.mark.asyncio
async def test_assign_quest_team_slot_uniqueness(async_session: AsyncSession) -> None:
    """Slots are numbered 1..n with no duplicates."""
    vault, quest = await _make_quest_vault(async_session)
    dwellers = [await _make_adult_dweller(async_session, vault) for _ in range(3)]

    members = await team_service.assign_quest_team(async_session, quest.id, vault.id, [d.id for d in dwellers])

    assert [member.slot_number for member in members] == [1, 2, 3]
    assert len({member.slot_number for member in members}) == 3


@pytest.mark.asyncio
async def test_assign_quest_team_rejects_unavailable_dwellers(async_session: AsyncSession) -> None:
    """Children, explorers, and deleted dwellers cannot join a team."""
    vault, quest = await _make_quest_vault(async_session)
    child_data = create_fake_dweller()
    child_data.update(is_adult=False, age_group=AgeGroupEnum.CHILD)
    child = Dweller(**child_data, vault_id=vault.id)
    explorer_data = create_fake_dweller()
    explorer_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT, status=DwellerStatusEnum.EXPLORING)
    explorer = Dweller(**explorer_data, vault_id=vault.id)
    deleted_data = create_fake_dweller()
    deleted_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT, is_deleted=True)
    deleted = Dweller(**deleted_data, vault_id=vault.id)
    async_session.add_all([child, explorer, deleted])
    await async_session.commit()

    with pytest.raises(ValidationException, match="not an adult"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [child.id])
    with pytest.raises(ValidationException, match="exploring"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [explorer.id])
    with pytest.raises(ValidationException, match="deleted"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [deleted.id])


@pytest.mark.asyncio
async def test_assign_quest_team_rejects_foreign_dweller(async_session: AsyncSession) -> None:
    """A dweller from another vault cannot join the team."""
    vault, quest = await _make_quest_vault(async_session)
    other_vault, _ = await _make_quest_vault(async_session, title="Other Vault Quest")
    foreign = await _make_adult_dweller(async_session, other_vault)

    with pytest.raises(ValidationException, match="does not belong to vault"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [foreign.id])


@pytest.mark.asyncio
async def test_assign_quest_team_questing_dweller_allowed_on_own_team(async_session: AsyncSession) -> None:
    """A QUESTING dweller may stay on the same quest's team, but not join another."""
    vault, quest = await _make_quest_vault(async_session)
    other_vault, other_quest = await _make_quest_vault(async_session, title="Other Quest")
    dweller = await _make_adult_dweller(async_session, vault)

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    # Same dweller, still QUESTING, re-assigned to the same quest: allowed.
    members = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    assert [member.dweller_id for member in members] == [dweller.id]

    # The same QUESTING dweller cannot join a different quest's team.
    await crud.quest_crud.assign_to_vault(async_session, other_quest.id, vault.id, is_visible=True)
    with pytest.raises(ValidationException, match="questing"):
        await team_service.assign_quest_team(async_session, other_quest.id, vault.id, [dweller.id])


@pytest.mark.asyncio
async def test_assign_quest_team_rejects_in_progress_quest(async_session: AsyncSession) -> None:
    """A started quest cannot acquire a new team."""
    vault, quest = await _make_quest_vault(async_session)
    dweller = await _make_adult_dweller(async_session, vault)
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    await quest_service.start_quest(async_session, quest.id, vault.id)

    with pytest.raises(ResourceConflictException, match="already in progress"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])


@pytest.mark.asyncio
async def test_assign_quest_team_requires_existing_quest_and_vault(async_session: AsyncSession) -> None:
    """Unknown quests and vaults are rejected before any mutation."""
    from uuid import uuid4

    vault, quest = await _make_quest_vault(async_session)
    dweller = await _make_adult_dweller(async_session, vault)

    with pytest.raises(ResourceNotFoundException, match="Quest"):
        await team_service.assign_quest_team(async_session, uuid4(), vault.id, [dweller.id])
    with pytest.raises(ResourceNotFoundException, match="Vault"):
        await team_service.assign_quest_team(async_session, quest.id, uuid4(), [dweller.id])


@pytest.mark.asyncio
async def test_quest_round_trip_assign_start_ready_claim(async_session: AsyncSession) -> None:
    """A full quest lifecycle: assign -> start -> ready -> claim, with status transitions."""
    from app.models.quest_reward import QuestReward, RewardType

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=10))
    dweller = await _make_adult_dweller(async_session, vault)

    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Round Trip Quest",
            short_description="Full lifecycle",
            long_description="Assign, start, ready, claim.",
            requirements="One adult dweller",
            rewards="50 caps",
            duration_minutes=60,
        ),
    )
    async_session.add(
        QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 50}, reward_chance=1.0)
    )
    link = await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    await async_session.commit()

    members = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    assert len(members) == 1
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.QUESTING

    await quest_service.start_quest(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    assert link.started_at is not None

    link.started_at = datetime.utcnow() - timedelta(minutes=61)
    link.duration_minutes = 60
    await async_session.commit()

    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert link.is_reward_ready is True
    assert dweller.status == DwellerStatusEnum.IDLE

    quest, granted = await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)
    assert quest.id == link.quest_id
    assert any(reward["reward_type"] == "caps" for reward in granted)
    await async_session.refresh(link)
    assert link.is_completed is True
