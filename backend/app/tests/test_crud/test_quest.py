from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import AgeGroupEnum, DwellerStatusEnum, RequirementType, RewardType
from app.core.event_bus import GameEvent, event_bus
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault_quest import VaultQuestCompletionLink
from app.models.weapon import Weapon
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.quest_duration import effective_quest_duration_minutes
from app.utils.time import utcnow

_QUEST = {"short_description": "Test", "long_description": "Test quest", "requirements": "None", "rewards": "None"}


async def _vault(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


async def _add_office(async_session: AsyncSession, vault_id: UUID) -> None:
    async_session.add(Room(**create_overseers_office(), vault_id=vault_id))
    await async_session.commit()


async def _quest(async_session: AsyncSession, title: str = "Quest", **kw):
    return await crud.quest_crud.create(async_session, obj_in=QuestCreate(**(_QUEST | {"title": title} | kw)))


async def _assign(async_session: AsyncSession, quest, vault, is_visible: bool = True):
    return await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=is_visible
    )


async def _offered_quest(async_session: AsyncSession, title: str = "Quest", *, office: bool = False, **kw):
    vault = await _vault(async_session)
    if office:
        await _add_office(async_session, vault.id)
    quest = await _quest(async_session, title, **kw)
    await _assign(async_session, quest, vault)
    return vault, quest


async def _dweller(async_session: AsyncSession, vault, **kw) -> Dweller:
    dweller = Dweller(**(create_fake_dweller() | {"age_group": AgeGroupEnum.ADULT} | kw), vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _party(async_session: AsyncSession, vault, quest, count: int = 1) -> list[Dweller]:
    dwellers = [await _dweller(async_session, vault) for _ in range(count)]
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [d.id for d in dwellers])
    return dwellers


async def test_assign_quest_twice_updates_visibility(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    quest = await _quest(async_session, "Double Assignment Test", requirements="Level 10 dwellers", rewards="150 caps")
    link1 = await _assign(async_session, quest, vault, is_visible=True)
    assert link1.is_visible is True
    # Second assignment (not visible) - should update existing link
    link2 = await _assign(async_session, quest, vault, is_visible=False)
    assert link2.vault_id == link1.vault_id
    assert link2.quest_id == link1.quest_id
    assert link2.is_visible is False


async def test_get_multi_for_vault(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    await _add_office(async_session, vault.id)
    quest1 = await _quest(async_session, "Quest 1", requirements="Level 5", rewards="50 caps")
    quest2 = await _quest(async_session, "Quest 2", requirements="Level 10", rewards="100 caps")
    async_session.add(
        QuestRequirement(
            quest_id=quest2.id,
            requirement_type=RequirementType.QUEST_COMPLETED,
            requirement_data={"quest_id": str(quest1.id)},
        )
    )
    await async_session.commit()
    quest3 = await _quest(async_session, "Quest 3", requirements="Level 15", rewards="150 caps")
    # All links begin visible; the requirement keeps quest2 locked until quest1 completes.
    for quest in (quest1, quest2, quest3):
        await _assign(async_session, quest, vault)
    quests = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    assert len(quests) == 3  # All three quests should be returned
    quest_dict = {q.title: q for q in quests}
    assert "Quest 1" in quest_dict
    assert quest_dict["Quest 1"].is_visible is True
    assert quest_dict["Quest 1"].duration_minutes == effective_quest_duration_minutes(quest1.duration_minutes)
    assert "Quest 2" in quest_dict
    assert quest_dict["Quest 2"].is_visible is True  # Offered; the lock reason explains the chain gate
    assert quest_dict["Quest 2"].is_locked is True
    assert quest_dict["Quest 2"].previous_quest_id == quest1.id
    assert "Quest 3" in quest_dict
    assert quest_dict["Quest 3"].is_visible is True
    quest_page_indexes = {}
    for page_index in range(3):
        page = await quest_service.get_quests_for_vault(async_session, vault.id, page_index, 1)
        assert len(page) == 1
        quest_page_indexes[page[0].title] = page_index
    assert quest_page_indexes["Quest 1"] != quest_page_indexes["Quest 2"]
    quest1_link = await async_session.get(crud.quest_crud.link_model, (vault.id, quest1.id))
    assert quest1_link is not None
    quest1_link.is_completed = True
    await async_session.commit()
    unlocked_quests = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    assert {quest.title: quest.is_visible for quest in unlocked_quests}["Quest 2"] is True
    quest2_page = await quest_service.get_quests_for_vault(async_session, vault.id, quest_page_indexes["Quest 2"], 1)
    assert quest2_page[0].title == "Quest 2"
    assert quest2_page[0].is_visible is True


async def test_get_multi_for_vault_with_requirements_and_rewards(async_session: AsyncSession) -> None:
    vault, quest = await _offered_quest(
        async_session, "Quest With Rewards", requirements="Level 10", rewards="100 caps"
    )
    async_session.add(
        QuestRequirement(quest_id=quest.id, requirement_type="level", requirement_data={"level": 10}, is_mandatory=True)
    )
    async_session.add(
        QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 100}, reward_chance=1.0)
    )
    await async_session.commit()
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)
    assert len(quests) == 1
    assert quests[0].quest_requirements is not None
    assert len(quests[0].quest_requirements) == 1
    assert quests[0].quest_requirements[0].requirement_type == "level"
    assert quests[0].quest_rewards is not None
    assert len(quests[0].quest_rewards) == 1
    assert quests[0].quest_rewards[0].reward_type == "caps"


async def test_get_multi_for_vault_serializes_completion_details(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    completed_quest = await _quest(async_session, "Completed Quest", short_description="Done", rewards="50 caps")
    fresh_quest = await _quest(async_session, "Fresh Quest", short_description="Not done", rewards="50 caps")
    await _assign(async_session, completed_quest, vault)
    await _assign(async_session, fresh_quest, vault)
    completed_link = await crud.quest_crud.get_link(async_session, quest_id=completed_quest.id, vault_id=vault.id)
    completed_link.is_completed = True
    completed_link.completed_at = utcnow()
    completed_link.granted_rewards = [{"reward_type": "caps", "amount": 50}]
    await async_session.commit()
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)
    by_title = {q.title: q for q in quests}
    assert by_title["Completed Quest"].completed_at is not None
    assert [r.model_dump(mode="json") for r in by_title["Completed Quest"].granted_rewards] == [
        {"reward_type": "caps", "amount": 50}
    ]
    assert by_title["Fresh Quest"].completed_at is None
    assert by_title["Fresh Quest"].granted_rewards is None


async def test_assign_party_rejects_ineligible_dwellers(async_session: AsyncSession) -> None:
    vault, quest = await _offered_quest(
        async_session, "Restricted Party Quest", requirements="1 dweller", rewards="100 caps"
    )
    child = await _dweller(async_session, vault, age_group=AgeGroupEnum.CHILD)
    explorer = await _dweller(async_session, vault, status=DwellerStatusEnum.EXPLORING)
    assigned = await _dweller(async_session, vault)
    deleted = await _dweller(async_session, vault, is_deleted=True)
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [assigned.id])
    with pytest.raises(ValidationException, match="not an adult"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [child.id])
    with pytest.raises(ValidationException, match="exploring"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [explorer.id])
    with pytest.raises(ValidationException, match="deleted"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [deleted.id])
    members = await crud.team_crud.get_quest_team(async_session, quest.id, vault.id)
    assert [member.dweller_id for member in members] == [assigned.id]


async def test_start_quest(async_session: AsyncSession) -> None:
    vault, quest = await _offered_quest(
        async_session, "Timed Quest", office=True, requirements="1 dweller", rewards="100 caps", duration_minutes=45
    )
    await _party(async_session, vault, quest)
    link = await quest_service.start_quest(async_session, quest.id, vault.id)
    assert link.started_at is not None
    assert link.duration_minutes == effective_quest_duration_minutes(quest.duration_minutes)
    with pytest.raises(ResourceConflictException, match="already in progress"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.parametrize(
    ("quest_kw", "match"),
    [
        ({"requirements": "Level 1"}, "Assign at least one dweller"),
        ({"requirements": "Level 1", "duration_minutes": 0}, "duration must be a positive value"),
    ],
    ids=["party-required", "positive-duration"],
)
async def test_start_quest_validation(async_session: AsyncSession, quest_kw: dict, match: str) -> None:
    vault, quest = await _offered_quest(async_session, "Guarded Quest", office=True, rewards="10 caps", **quest_kw)
    with pytest.raises(ValidationException, match=match):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.parametrize("quest_category", ["building", "population", "training"])
async def test_start_state_quest_is_ready_without_a_party(async_session: AsyncSession, quest_category: str) -> None:
    vault, quest = await _offered_quest(
        async_session,
        f"{quest_category.title()} objective",
        requirements="Existing vault progress",
        rewards="100 caps",
        quest_category=quest_category,
    )
    link = await quest_service.start_quest(async_session, quest.id, vault.id)
    assert link.is_reward_ready is True
    assert link.started_at is None


async def test_quest_cannot_complete_before_its_duration(async_session: AsyncSession) -> None:
    # Manual completion must not bypass a running quest's timer.
    vault, quest = await _offered_quest(
        async_session, "No Early Return", office=True, requirements="Level 1", rewards="10 caps", duration_minutes=60
    )
    await _party(async_session, vault, quest)
    await quest_service.start_quest(async_session, quest.id, vault.id)
    with pytest.raises(ValidationException, match="not ready to claim"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)


async def test_timed_quest_completion_simulation(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=10))
    dweller_data = create_fake_dweller() | {"age_group": AgeGroupEnum.ADULT, "level": 1, "experience": 0}
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    quest = await _quest(
        async_session,
        "Timed reward simulation",
        requirements="One adult dweller",
        rewards="50 caps and a laser pistol",
        duration_minutes=120,
    )
    async_session.add_all(
        [
            QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 50}, reward_chance=1.0),
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType.ITEM,
                reward_data={"item_type": "weapon", "name": "Laser Pistol"},
            ),
        ]
    )
    link = await _assign(async_session, quest, vault)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    link.started_at = utcnow() - timedelta(minutes=61)
    link.duration_minutes = 60
    await async_session.commit()
    assert await quest_service.check_and_complete_quests(async_session) == 0
    await async_session.refresh(link)
    assert link.return_completes_at is not None
    assert link.is_reward_ready is False
    link.return_completes_at = utcnow() - timedelta(seconds=1)
    await async_session.commit()
    assert await quest_service.check_and_complete_quests(async_session) == 1
    await async_session.refresh(link)
    assert link.is_completed is False
    assert link.is_reward_ready is True
    assert vault.bottle_caps == vault_data["bottle_caps"]
    assert dweller.status == DwellerStatusEnum.IDLE
    events = []

    async def capture_event(_event_type, _vault_id, data) -> None:
        events.append(data)

    event_bus.subscribe(GameEvent.QUEST_COMPLETED, capture_event)
    try:
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)
    finally:
        event_bus.unsubscribe(GameEvent.QUEST_COMPLETED, capture_event)
    await async_session.refresh(link)
    await async_session.refresh(vault)
    await async_session.refresh(dweller)
    weapon = (await async_session.execute(select(Weapon).where(Weapon.name == "Laser pistol"))).scalar_one()
    assert link.is_completed is True
    assert weapon.storage_id is not None
    assert dweller.level == 5
    assert dweller.experience == 1200
    assert events == [{"quest_id": str(quest.id), "quest_title": quest.title, "quest_type": quest.quest_type.value}]
    with pytest.raises(ResourceConflictException, match="Already completed"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == vault_data["bottle_caps"] + 50


async def test_get_multi_for_vault_auto_assigns_quests(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    by_type = {
        "side": "Auto Side Quest",
        "daily": "Auto Daily Quest",
        "repeatable": "Auto Weekly Quest",
        "event": "Auto Event Quest",
    }
    for quest_type, title in by_type.items():
        await _quest(
            async_session,
            title,
            short_description="Auto-assign fixture",
            long_description="Backfill visibility defaults per quest type.",
            requirements="No prerequisites",
            rewards="10 caps",
            quest_type=quest_type,
        )
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)
    assert len(quests) == len(by_type)
    visibility = {q.title: q.is_visible for q in quests}
    assert visibility["Auto Side Quest"] is True
    for scheduled in ("Auto Daily Quest", "Auto Weekly Quest", "Auto Event Quest"):
        assert visibility[scheduled] is False, scheduled


async def test_assign_party_replaces_existing(async_session: AsyncSession) -> None:
    vault, quest = await _offered_quest(
        async_session, "Replace Party Quest", office=True, requirements="2 dwellers", rewards="200 caps"
    )
    dweller1, dweller2, dweller3 = [await _dweller(async_session, vault) for _ in range(3)]
    members1 = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller1.id, dweller2.id])
    assert len(members1) == 2
    assert members1[0].dweller_id == dweller1.id
    members2 = await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller3.id])
    assert len(members2) == 1
    assert members2[0].dweller_id == dweller3.id
    await quest_service.start_quest(async_session, quest.id, vault.id)
    with pytest.raises(ResourceConflictException, match="already in progress"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller1.id])


@pytest.mark.parametrize("link_state", [{"is_reward_ready": True}, {"is_completed": True}])
async def test_assign_party_rejects_reward_ready_or_completed_quest(
    async_session: AsyncSession, link_state: dict[str, bool]
) -> None:
    vault = await _vault(async_session)
    quest = await _quest(async_session, "Finished Objective", requirements="None", rewards="None")
    dweller = await _dweller(async_session, vault)
    async_session.add(VaultQuestCompletionLink(vault_id=vault.id, quest_id=quest.id, **link_state))
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="already in progress"):
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])


def test_link_return_leg_helpers() -> None:
    link = VaultQuestCompletionLink(vault_id=uuid4(), quest_id=uuid4())
    assert link.is_returning() is False
    assert link.return_time_remaining_seconds() == 0
    link.start_return(30)
    assert link.return_started_at is not None
    assert link.return_completes_at is not None
    assert link.is_returning() is True
    assert 1790 <= link.return_time_remaining_seconds() <= 1800
    link.is_reward_ready = True
    assert link.is_returning() is False
    assert link.return_time_remaining_seconds() == 0


async def test_get_expired_party_links_excludes_returning(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)

    async def _expired_link(title: str, *, returning: bool) -> VaultQuestCompletionLink:
        quest = await _quest(async_session, title, duration_minutes=60)
        await _assign(async_session, quest, vault)
        link = await crud.quest_crud.get_link(async_session, quest_id=quest.id, vault_id=vault.id)
        link.started_at = utcnow() - timedelta(minutes=120)
        link.duration_minutes = 60
        if returning:
            link.start_return(30)
        await async_session.commit()
        return link

    expired = await _expired_link("Expired Party", returning=False)
    returning = await _expired_link("Returning Party", returning=True)
    duration_minutes = func.coalesce(VaultQuestCompletionLink.duration_minutes, Quest.duration_minutes)
    expires_at = func.datetime(VaultQuestCompletionLink.started_at, func.printf("+%s minutes", duration_minutes))
    links = await crud.quest_crud.get_expired_party_links(async_session, now=utcnow(), expires_at=expires_at)
    assert {link.quest_id for link in links} == {expired.quest_id}
    assert returning.quest_id not in {link.quest_id for link in links}


async def test_get_arrived_party_links(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)

    async def _link(title: str, *, return_completes_at: datetime, **flags) -> VaultQuestCompletionLink:
        quest = await _quest(async_session, title, duration_minutes=60)
        link = VaultQuestCompletionLink(
            vault_id=vault.id,
            quest_id=quest.id,
            is_visible=True,
            started_at=utcnow() - timedelta(minutes=120),
            duration_minutes=60,
            return_started_at=utcnow() - timedelta(minutes=30),
            return_completes_at=return_completes_at,
            **flags,
        )
        async_session.add(link)
        await async_session.commit()
        return link

    now = utcnow()
    arrived = await _link("Arrived Party", return_completes_at=now - timedelta(minutes=1))
    travelling = await _link("Travelling Party", return_completes_at=now + timedelta(minutes=30))
    ready = await _link("Ready Party", return_completes_at=now - timedelta(minutes=1), is_reward_ready=True)
    completed = await _link("Completed Party", return_completes_at=now - timedelta(minutes=1), is_completed=True)
    links = await crud.quest_crud.get_arrived_party_links(async_session, now=now)
    assert {link.quest_id for link in links} == {arrived.quest_id}
    assert travelling.quest_id not in {link.quest_id for link in links}
    assert ready.quest_id not in {link.quest_id for link in links}
    assert completed.quest_id not in {link.quest_id for link in links}


async def test_get_link_for_update_returns_committed_state(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    quest = await _quest(async_session, "Locked Read")
    await _assign(async_session, quest, vault)
    link = await crud.quest_crud.get_link_for_update(async_session, quest_id=quest.id, vault_id=vault.id)
    assert link is not None
    assert link.quest_id == quest.id
    assert link.vault_id == vault.id
    link.is_reward_ready = True
    await async_session.commit()
    refreshed = await crud.quest_crud.get_link_for_update(async_session, quest_id=quest.id, vault_id=vault.id)
    assert refreshed is not None
    assert refreshed.is_reward_ready is True
    assert await crud.quest_crud.get_link_for_update(async_session, quest_id=uuid4(), vault_id=vault.id) is None


async def test_get_quests_for_vault_paginates_beyond_the_first_page(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    await _add_office(async_session, vault.id)
    quests = [
        Quest(
            title=f"Paginated side {number}",
            short_description="Pagination fixture",
            long_description="Catalog growth must not hide quests past the first page.",
            requirements="No prerequisites",
            rewards="10 caps",
            duration_minutes=60,
        )
        for number in range(150)
    ]
    async_session.add_all(quests)
    await async_session.commit()
    offer, party, ready = quests[100], quests[101], quests[102]
    async_session.add_all(
        [
            VaultQuestCompletionLink(vault_id=vault.id, quest_id=offer.id, is_visible=True),
            VaultQuestCompletionLink(
                vault_id=vault.id, quest_id=party.id, is_visible=True, started_at=utcnow(), duration_minutes=60
            ),
            VaultQuestCompletionLink(
                vault_id=vault.id, quest_id=ready.id, is_visible=True, is_reward_ready=True, started_at=utcnow()
            ),
        ]
    )
    await async_session.commit()
    first_page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    assert len(first_page) == 100
    page_two = await quest_service.get_quests_for_vault(async_session, vault.id, 100, 100)
    assert {quest_read.id for quest_read in page_two} == {quest.id for quest in quests[100:]}
    states = {quest_read.id: quest_read for quest_read in page_two}
    assert states[offer.id].is_visible
    assert states[offer.id].started_at is None
    assert states[party.id].started_at is not None
    assert states[ready.id].is_reward_ready
