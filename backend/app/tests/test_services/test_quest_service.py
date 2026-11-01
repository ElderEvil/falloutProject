"""Tests for quest availability unification (read/start agreement + Office rule)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import RequirementType
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.quests.service import quest_service
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


async def _vault_with_office(async_session: AsyncSession, tier: int = 1):
    """A vault that has built the Overseer's Office."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(tier=tier), vault_id=vault.id))
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
    assert availability.lock_reason == "Complete 'Chain Starter' first"

    await crud.quest_crud.assign_to_vault(async_session, quest_a.id, vault.id, is_visible=True)
    link = await crud.quest_crud.get_link(async_session, quest_id=quest_a.id, vault_id=vault.id)
    link.is_completed = True
    await async_session.commit()

    availability = await quest_service.get_quest_availability(async_session, vault.id, quest_b)
    assert availability.available is True
    assert availability.lock_reason is None


@pytest.mark.asyncio
async def test_chain_lock_reason_names_the_predecessor_on_the_read_path(async_session: AsyncSession) -> None:
    """The vault quest read surfaces which quest gates a chain follow-up."""
    vault = await _vault_with_office(async_session)
    quest_a = await _create_quest(async_session, title="Getting Started")
    quest_b = await _create_quest(async_session, title="Next Steps", previous_quest_id=quest_a.id)
    await crud.quest_crud.assign_to_vault(async_session, quest_a.id, vault.id, is_visible=True)
    await crud.quest_crud.assign_to_vault(async_session, quest_b.id, vault.id, is_visible=True)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    follow_up = next(q for q in quest_reads if q.title == "Next Steps")

    assert follow_up.is_locked is True
    assert follow_up.lock_reason == "Complete 'Getting Started' first"


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
async def test_available_only_returns_full_page_past_locked_quests(async_session: AsyncSession) -> None:
    """available_only filters availability before pagination, so locked quests never starve a page."""
    from uuid import uuid4

    vault = await _vault_with_office(async_session)
    locked = [await _create_quest(async_session, title=f"Locked {i}", previous_quest_id=uuid4()) for i in range(3)]
    available = [await _create_quest(async_session, title=f"Open {i}") for i in range(3)]
    for quest in [*locked, *available]:
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 3, available_only=True)

    assert len(page) == 3
    assert all(not q.is_locked for q in page)
    assert {q.title for q in page} == {"Open 0", "Open 1", "Open 2"}


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


async def _vault_with_level_dweller(async_session: AsyncSession, level: int):
    """A vault with the Overseer's Office and one adult dweller at ``level``."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller

    vault = await _vault_with_office(async_session)
    dweller_data = create_fake_adult_dweller()
    dweller_data["level"] = level
    async_session.add(Dweller(**dweller_data, vault_id=vault.id))
    await async_session.commit()
    return vault


@pytest.mark.asyncio
async def test_level_gated_quest_hidden_beyond_reveal_margin(async_session: AsyncSession) -> None:
    """A quest whose mandatory LEVEL gate is far above the vault's max dweller level is hidden entirely."""
    vault = await _vault_with_level_dweller(async_session, level=20)
    quest = await _create_quest(async_session, title="Level 46 Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)

    assert all(q.id != quest.id for q in quest_reads)


@pytest.mark.asyncio
async def test_level_gated_quest_visible_within_reveal_margin(async_session: AsyncSession) -> None:
    """A quest whose LEVEL gate is within the reveal margin shows as locked, not hidden."""
    vault = await _vault_with_level_dweller(async_session, level=20)
    quest = await _create_quest(async_session, title="Level 30 Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 30},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is True
    assert quest_read.is_visible is False
    assert "level" in quest_read.lock_reason


@pytest.mark.asyncio
async def test_level_gated_quest_available_with_qualifying_dweller(async_session: AsyncSession) -> None:
    """A vault with a dweller at the required level sees the quest available."""
    vault = await _vault_with_level_dweller(async_session, level=46)
    quest = await _create_quest(async_session, title="Level 46 Available")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is False
    assert quest_read.is_visible is True


@pytest.mark.asyncio
async def test_available_only_respects_level_reveal(async_session: AsyncSession) -> None:
    """available_only also hides quests beyond the reveal margin."""
    vault = await _vault_with_level_dweller(async_session, level=20)
    hidden = await _create_quest(async_session, title="Hidden Level 46")
    async_session.add(
        QuestRequirement(
            quest_id=hidden.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    open_quest = await _create_quest(async_session, title="Open Quest")
    await async_session.commit()
    for quest in (hidden, open_quest):
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100, available_only=True)

    assert all(q.id != hidden.id for q in page)
    assert {q.title for q in page} == {"Open Quest"}


@pytest.mark.asyncio
async def test_level_gated_quest_shown_locked_without_office(async_session: AsyncSession) -> None:
    """Without the Overseer's Office a far level-gated quest is shown locked, not hidden by reveal."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_data = create_fake_adult_dweller()
    dweller_data["level"] = 20
    async_session.add(Dweller(**dweller_data, vault_id=vault.id))
    quest = await _create_quest(async_session, title="No Office Level 46")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is True
    assert quest_read.lock_reason == "Requires Overseer's Office"


@pytest.mark.asyncio
async def test_normal_read_fills_page_past_hidden_quests(async_session: AsyncSession) -> None:
    """The normal quest read paginates after reveal/availability filtering, so a page is full of visible quests."""
    vault = await _vault_with_level_dweller(async_session, level=20)
    hidden = await _create_quest(async_session, title="Hidden Level 46")
    async_session.add(
        QuestRequirement(
            quest_id=hidden.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    open_quests = [await _create_quest(async_session, title=f"Open {i}") for i in range(4)]
    await async_session.commit()
    for quest in (hidden, *open_quests):
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 3)

    assert len(page) == 3
    assert all(q.id != hidden.id for q in page)
    assert {q.title for q in page} <= {"Open 0", "Open 1", "Open 2", "Open 3"}


@pytest.mark.asyncio
async def test_item_requirement_met_by_equipped_item(async_session: AsyncSession) -> None:
    """The read-path ITEM check counts items equipped by vault dwellers, not only storage."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Equipped Item Read")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Laser Pistol"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["name"] = "Laser Pistol"
    weapon_data["dweller_id"] = dweller.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is False
    assert quest_read.is_visible is True


@pytest.mark.asyncio
async def test_start_quest_rejects_party_below_level_requirement(async_session: AsyncSession) -> None:
    """A party of level-40 dwellers cannot start a quest requiring level 46."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.utils.exceptions import ValidationException

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Level 46 Party Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller_data["level"] = 40
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    with pytest.raises(ValidationException, match="level 46"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_with_level_qualifying_party(async_session: AsyncSession) -> None:
    """Adding a level-46 member lets the party start the level-46 quest."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Level 46 Party Pass")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    low_data = create_fake_adult_dweller()
    low_data["level"] = 40
    high_data = create_fake_adult_dweller()
    high_data["level"] = 46
    low = Dweller(**low_data, vault_id=vault.id)
    high = Dweller(**high_data, vault_id=vault.id)
    async_session.add_all([low, high])
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [low.id, high.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
async def test_start_quest_rejects_missing_required_item(async_session: AsyncSession) -> None:
    """A quest whose required item exists nowhere in the vault cannot start."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.utils.exceptions import ValidationException

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Item Party Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Laser Pistol"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    with pytest.raises(ValidationException, match="Laser Pistol"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_with_required_item_equipped_in_vault(async_session: AsyncSession) -> None:
    """An item equipped by a vault dweller lets the quest start."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Item Party Pass")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Laser Pistol"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["name"] = "Laser Pistol"
    weapon_data["dweller_id"] = dweller.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
async def test_start_quest_accepts_required_outfit_equipped_by_a_vault_dweller(async_session: AsyncSession) -> None:
    """An outfit equipped by any vault dweller satisfies ITEM, matching the read path.

    The read path counts items equipped by vault dwellers (not only storage), so the start path
    must agree: a quest that reads as available must not be rejected for an outfit another
    dweller is wearing. Regression: "Ghoul in Black" refused to start though a dweller wore the
    Vault 33 suit, because the start path demanded it on a dispatched party member.
    """
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_outfit

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Equipped Outfit Start")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Vault 33 suit"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    wearer = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(wearer)
    await async_session.commit()

    outfit_data = create_fake_outfit()
    outfit_data["name"] = "Vault 33 suit"
    outfit_data["dweller_id"] = wearer.id
    await crud.outfit.create(async_session, obj_in=outfit_data)

    party_member = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(party_member)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [party_member.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
async def test_start_quest_rejects_party_below_attack(async_session: AsyncSession) -> None:
    """A party whose weapons deal below the required attack cannot start the quest."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon
    from app.utils.exceptions import ValidationException

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Attack Party Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ATTACK,
            requirement_data={"attack": 20},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["damage_min"] = 5
    weapon_data["damage_max"] = 10
    weapon_data["dweller_id"] = dweller.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    with pytest.raises(ValidationException, match="20"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_with_attack_qualifying_party(async_session: AsyncSession) -> None:
    """A party member with a weapon meeting the attack threshold lets the quest start."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Attack Party Pass")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ATTACK,
            requirement_data={"attack": 20},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["damage_min"] = 15
    weapon_data["damage_max"] = 25
    weapon_data["dweller_id"] = dweller.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
async def test_attack_requirement_met_by_equipped_weapon(async_session: AsyncSession) -> None:
    """The read-path ATTACK check counts dwellers with a qualifying equipped weapon."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Attack Read")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ATTACK,
            requirement_data={"attack": 20},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["damage_min"] = 15
    weapon_data["damage_max"] = 25
    weapon_data["dweller_id"] = dweller.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is False
    assert quest_read.is_visible is True


@pytest.mark.asyncio
async def test_dead_dweller_does_not_unlock_read_path_requirements(async_session: AsyncSession) -> None:
    """Dead dwellers do not satisfy read-path LEVEL/ATTACK availability (living invariant)."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_weapon

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Living Only Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 46},
            is_mandatory=True,
        )
    )
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ATTACK,
            requirement_data={"attack": 20},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    living_data = create_fake_adult_dweller()
    living_data["level"] = 40
    dead_data = create_fake_adult_dweller()
    dead_data["level"] = 46
    dead_data["is_dead"] = True
    living = Dweller(**living_data, vault_id=vault.id)
    dead = Dweller(**dead_data, vault_id=vault.id)
    async_session.add_all([living, dead])
    await async_session.commit()

    weapon_data = create_fake_weapon()
    weapon_data["damage_min"] = 15
    weapon_data["damage_max"] = 25
    weapon_data["dweller_id"] = dead.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is True
    assert "level" in quest_read.lock_reason
    assert "attack" in quest_read.lock_reason


@pytest.mark.asyncio
async def test_start_quest_rejects_party_below_stat(async_session: AsyncSession) -> None:
    """A party whose members lack the required SPECIAL stat cannot start the quest."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.utils.exceptions import ValidationException

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Stat Party Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.STAT,
            requirement_data={"stat": "strength", "value": 6},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller_data["strength"] = 3
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    with pytest.raises(ValidationException, match="Strength"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_with_stat_qualifying_party(async_session: AsyncSession) -> None:
    """A party member with the required SPECIAL stat lets the quest start."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Stat Party Pass")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.STAT,
            requirement_data={"stat": "strength", "value": 6},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller_data["strength"] = 6
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
async def test_stat_requirement_met_by_qualifying_dweller(async_session: AsyncSession) -> None:
    """The read-path STAT check counts living dwellers with the effective stat."""
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_adult_dweller

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Stat Read")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.STAT,
            requirement_data={"stat": "strength", "value": 6},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dweller_data = create_fake_adult_dweller()
    dweller_data["strength"] = 6
    async_session.add(Dweller(**dweller_data, vault_id=vault.id))
    await async_session.commit()

    quest_reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next(q for q in quest_reads if q.id == quest.id)

    assert quest_read.is_locked is False
    assert quest_read.is_visible is True


def test_quest_service_facade_reexports_canonical_surface() -> None:
    """The top-level facade forwards the canonical module's public names by identity."""
    from app.services import quest_service as facade
    from app.services.progression.quests import availability
    from app.services.progression.quests import service as canonical

    for name in ("QuestAvailability", "OFFICE_ROOM_TYPE", "OFFICE_LOCK_REASON", "CHAIN_LOCK_REASON", "REVEAL_MARGIN"):
        assert getattr(facade, name) is getattr(availability, name)
    assert facade.QuestService is canonical.QuestService
    assert facade.quest_service is canonical.quest_service


@pytest.mark.asyncio
async def test_item_requirement_read_and_start_agree_for_non_party_wearer(
    async_client, async_session: AsyncSession
) -> None:
    """A quest reads available and starts when a non-party dweller wears the required item.

    Regression: "Ghoul in Black" read as startable because a vault dweller wore the Vault 33
    suit, but the start path demanded the item on a dispatched party member and refused with 400.
    """
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_outfit
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    await async_session.commit()

    quest = await _create_quest(async_session, title="Non-Party Wearer Agreement")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Vault 33 suit"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    wearer = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(wearer)
    await async_session.commit()

    outfit_data = create_fake_outfit()
    outfit_data["name"] = "Vault 33 suit"
    outfit_data["dweller_id"] = wearer.id
    await crud.outfit.create(async_session, obj_in=outfit_data)

    party_member = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(party_member)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [party_member.id])

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    read_response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert read_response.status_code == 200, f"Expected 200, got {read_response.status_code}: {read_response.text}"
    quest_read = next(q for q in read_response.json() if q["id"] == str(quest.id))
    assert quest_read["is_locked"] is False
    # Per-row verdicts ride along on the read, so the UI can show which gate blocks what.
    item_row = next(r for r in quest_read["quest_requirements"] if r["requirement_type"] == "item")
    assert item_row["is_met"] is True

    start_response = await async_client.post(f"/quests/{vault.id}/{quest.id}/start", headers=headers)
    assert start_response.status_code == 200, f"Expected 200, got {start_response.status_code}: {start_response.text}"


@pytest.mark.asyncio
async def test_start_quest_rejects_item_equipped_only_by_dead_dweller(async_session: AsyncSession) -> None:
    """A dead dweller's worn outfit does not satisfy the vault-scoped ITEM gate."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_outfit
    from app.utils.exceptions import ValidationException

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Dead Wearer Item Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Vault 33 suit"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    dead_data = create_fake_adult_dweller()
    dead_data["is_dead"] = True
    dead_wearer = Dweller(**dead_data, vault_id=vault.id)
    async_session.add(dead_wearer)
    await async_session.commit()

    outfit_data = create_fake_outfit()
    outfit_data["name"] = "Vault 33 suit"
    outfit_data["dweller_id"] = dead_wearer.id
    await crud.outfit.create(async_session, obj_in=outfit_data)

    party_member = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(party_member)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [party_member.id])

    with pytest.raises(ValidationException, match="Vault 33 suit"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_matches_required_item_case_insensitively(async_session: AsyncSession) -> None:
    """The vault-scoped ITEM gate matches the required name case-insensitively."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.tests.factory.items import create_fake_outfit

    vault = await _vault_with_office(async_session)
    quest = await _create_quest(async_session, title="Case-Insensitive Item Gate")
    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Vault 33 suit"},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    wearer = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(wearer)
    await async_session.commit()

    outfit_data = create_fake_outfit()
    outfit_data["name"] = "vault 33 SUIT"
    outfit_data["dweller_id"] = wearer.id
    await crud.outfit.create(async_session, obj_in=outfit_data)

    party_member = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(party_member)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [party_member.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("running_count", [2, 3])
async def test_timed_quest_limit_counts_outbound_and_returning_only(async_session: AsyncSession, running_count: int):
    from datetime import datetime, timedelta

    from app.models.dweller import Dweller
    from app.models.vault_quest import VaultQuestCompletionLink
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.utils.exceptions import ResourceConflictException

    vault = await _vault_with_office(async_session, tier=3)
    other_vault = await _vault_with_office(async_session, tier=3)
    now = datetime.utcnow()
    for index in range(running_count + 3):
        quest = await _create_quest(async_session, title=f"Existing {index}")
        if index == 0:
            first_quest_id = quest.id
        quest.quest_category = "training" if index == running_count + 2 else "combat"
        async_session.add(quest)
        async_session.add(
            VaultQuestCompletionLink(
                quest_id=quest.id,
                vault_id=vault.id,
                started_at=now,
                duration_minutes=60,
                return_started_at=now if index == 0 else None,
                return_completes_at=now + timedelta(minutes=10) if index == 0 else None,
                is_reward_ready=index == running_count,
                is_completed=index == running_count + 1,
            )
        )
        async_session.add(
            VaultQuestCompletionLink(
                quest_id=quest.id,
                vault_id=other_vault.id,
                started_at=now,
                duration_minutes=60,
            )
        )
        await async_session.commit()

    candidate = await _create_quest(async_session, title="Next timed quest")
    await crud.quest_crud.assign_to_vault(async_session, candidate.id, vault.id, is_visible=True)
    dweller = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, candidate.id, vault.id, [dweller.id])

    if running_count == 3:
        with pytest.raises(ResourceConflictException, match="3 quest slots"):
            await quest_service.start_quest(async_session, candidate.id, vault.id)
        link = await crud.quest_crud.get_link(async_session, quest_id=candidate.id, vault_id=vault.id)
        assert link.started_at is None
    else:
        link = await quest_service.start_quest(async_session, candidate.id, vault.id)
        assert link.started_at is not None

    state_quest = await _create_quest(async_session, title="State quest at capacity")
    state_quest.quest_category = "building"
    async_session.add(state_quest)
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, state_quest.id, vault.id, is_visible=True)
    state_link = await quest_service.start_quest(async_session, state_quest.id, vault.id)
    assert state_link.is_reward_ready
    assert state_link.started_at is None

    if running_count == 3:
        returning = await crud.quest_crud.get_link(async_session, quest_id=first_quest_id, vault_id=vault.id)
        returning.is_reward_ready = True
        await async_session.commit()
        started = await quest_service.start_quest(async_session, candidate.id, vault.id)
        assert started.started_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("office_tier", [1, 2, 3])
async def test_quest_slots_follow_office_tier(async_session: AsyncSession, office_tier: int) -> None:
    """A tier-N office allows N simultaneous timed quests and shortens their duration."""
    from app.models.dweller import Dweller
    from app.services.team_service import team_service
    from app.tests.factory.dwellers import create_fake_adult_dweller
    from app.utils.exceptions import ResourceConflictException
    from app.utils.quest_duration import effective_quest_duration_minutes

    vault = await _vault_with_office(async_session, tier=office_tier)

    first_link = None
    for index in range(office_tier):
        quest = await _create_quest(async_session, title=f"Tier quest {index}")
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
        dweller = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
        async_session.add(dweller)
        await async_session.commit()
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
        link = await quest_service.start_quest(async_session, quest.id, vault.id)
        first_link = first_link or link

    assert first_link is not None
    assert first_link.duration_minutes == effective_quest_duration_minutes(60, office_tier=office_tier)

    overflow = await _create_quest(async_session, title="One too many")
    await crud.quest_crud.assign_to_vault(async_session, overflow.id, vault.id, is_visible=True)
    dweller = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, overflow.id, vault.id, [dweller.id])

    with pytest.raises(ResourceConflictException, match=f"All {office_tier} quest slots"):
        await quest_service.start_quest(async_session, overflow.id, vault.id)
