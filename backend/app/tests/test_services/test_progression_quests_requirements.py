"""Tests for the quest requirement policy (``progression.quests.requirements``)."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.room import Room
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.quests import requirements
from app.services.progression.quests.requirements import (
    party_missing_requirements,
    validate_dweller_count_requirement,
    validate_quest_completed_requirement,
    validate_room_requirement,
    vault_missing_requirements,
)
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


def _make_req(requirement_type: RequirementType, requirement_data: dict, *, is_mandatory: bool = True) -> object:
    return SimpleNamespace(
        requirement_type=requirement_type, requirement_data=requirement_data, is_mandatory=is_mandatory
    )


def _make_quest(*reqs: object) -> object:
    return SimpleNamespace(title="Test Quest", quest_requirements=list(reqs))


def _party_dweller(**attrs: object) -> object:
    """Transient dweller stand-in for the pure party gates (no DB needed)."""
    defaults: dict[str, object] = {
        "level": 1,
        "strength": 1,
        "perception": 1,
        "endurance": 1,
        "charisma": 1,
        "intelligence": 1,
        "agility": 1,
        "luck": 1,
        "weapon": None,
        "outfit": None,
        "visual_attributes": None,
    }
    defaults.update(attrs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
@pytest.mark.parametrize("room_name", ["Living room", "Living Quarters"])
async def test_validate_room_requirement_accepts_living_quarters_alias(
    async_session: AsyncSession, room_name: str
) -> None:
    """Both Living Quarters labels satisfy the seeded living_quarter requirement."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(
        Room(
            name=room_name,
            category=RoomTypeEnum.CAPACITY,
            ability=SPECIALEnum.CHARISMA,
            base_cost=100,
            size_min=1,
            size_max=3,
            vault_id=vault.id,
        )
    )
    await async_session.commit()

    assert await validate_room_requirement(async_session, vault.id, {"room_type": "living_quarter"}) is True


@pytest.mark.asyncio
async def test_validate_dweller_count_requirement_not_met(async_session: AsyncSession) -> None:
    """Test dweller count requirement with not enough dwellers."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create 2 dwellers
    for i in range(2):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    result = await validate_dweller_count_requirement(async_session, vault.id, {"count": 5})
    assert result is False


@pytest.mark.asyncio
async def test_validate_quest_completed_requirement_not_met(async_session: AsyncSession) -> None:
    """Test quest completed requirement when quest not done."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create prerequisite quest
    prereq_quest = Quest(
        title="Prerequisite Quest",
        short_description="Test",
        long_description="Test",
        requirements="None",
        rewards="None",
        quest_type="side",
    )
    async_session.add(prereq_quest)
    await async_session.commit()
    await async_session.refresh(prereq_quest)

    # Not marking as completed

    result = await validate_quest_completed_requirement(async_session, vault.id, {"quest_id": prereq_quest.id})
    assert result is False


@pytest.mark.asyncio
async def test_vault_missing_requirements(async_session: AsyncSession) -> None:
    """Test vault_missing_requirements returns human-readable descriptions."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create quest
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="Level 100 dweller",
        rewards="1000 caps",
        quest_type="main",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add unmet requirement
    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 100, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()
    await async_session.refresh(quest)
    await async_session.refresh(quest, ["quest_requirements"])

    missing = await vault_missing_requirements(async_session, vault.id, quest)

    assert len(missing) > 0
    assert any("level" in desc.lower() for desc in missing)


@pytest.mark.asyncio
async def test_vault_missing_requirements_empty(async_session: AsyncSession) -> None:
    """A quest with no requirements is never gated."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="No Requirements",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)
    await async_session.refresh(quest, ["quest_requirements"])

    assert await vault_missing_requirements(async_session, vault.id, quest) == []


@pytest.mark.asyncio
async def test_vault_missing_requirements_omits_optional(async_session: AsyncSession) -> None:
    """An unmet *optional* requirement is skipped, never reported missing."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Optional Gate",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 999, "count": 1},
            is_mandatory=False,
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])

    assert await vault_missing_requirements(async_session, vault.id, quest) == []


@pytest.mark.asyncio
async def test_vault_missing_requirements_unknown_type_fails_closed() -> None:
    """An unhandled requirement type is logged and treated as unmet, never raised."""
    quest = _make_quest(_make_req("bogus", {}))
    missing = await vault_missing_requirements(None, uuid4(), quest)
    assert missing == ["Unknown requirement: bogus"]


@pytest.mark.asyncio
async def test_vault_missing_requirements_validator_error_fails_closed(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validator exception is logged and the gate fails closed (reported missing)."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Boom Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.LEVEL,
            requirement_data={"level": 100, "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])

    async def _boom(_db_session: object, _vault_id: object, requirement_data: dict) -> bool:
        raise RuntimeError("validator exploded")

    monkeypatch.setattr(requirements, "validate_level_requirement", _boom)

    missing = await vault_missing_requirements(async_session, vault.id, quest)
    assert missing == ["Need a dweller at level 100 or higher"]


def test_party_missing_requirements_level_gate() -> None:
    """LEVEL gates evaluate against the dispatched party; optional gates are skipped."""
    party = [_party_dweller(level=5), _party_dweller(level=6)]
    quest = _make_quest(
        _make_req(RequirementType.LEVEL, {"level": 5, "count": 2}),
        _make_req(RequirementType.LEVEL, {"level": 99, "count": 1}, is_mandatory=False),
    )
    assert party_missing_requirements(party, quest) == []

    quest = _make_quest(_make_req(RequirementType.LEVEL, {"level": 7, "count": 1}))
    assert party_missing_requirements(party, quest) == ["Need a dweller at level 7 or higher"]


def test_party_missing_requirements_item_gate() -> None:
    """ITEM gates match equipped weapon/outfit names on the party."""
    party = [_party_dweller(weapon=SimpleNamespace(name="10mm Pistol"))]
    quest = _make_quest(_make_req(RequirementType.ITEM, {"item_name": "10mm Pistol", "count": 1}))
    assert party_missing_requirements(party, quest) == []

    quest = _make_quest(_make_req(RequirementType.ITEM, {"item_name": "Vault Suit", "count": 1}))
    assert party_missing_requirements(party, quest) == ["Need a party dweller equipped with Vault Suit"]


def test_party_missing_requirements_attack_gate() -> None:
    """ATTACK gates use the equipped weapon's average damage on the party."""
    party = [_party_dweller(weapon=SimpleNamespace(name="Rifle", damage_min=10, damage_max=30))]
    quest = _make_quest(_make_req(RequirementType.ATTACK, {"attack": 20, "count": 1}))
    assert party_missing_requirements(party, quest) == []

    quest = _make_quest(_make_req(RequirementType.ATTACK, {"attack": 21, "count": 1}))
    assert party_missing_requirements(party, quest) == ["Need a party dweller with 21+ attack"]


def test_party_missing_requirements_stat_gate() -> None:
    """STAT gates use effective SPECIAL values (outfit bonus included) on the party."""
    party = [_party_dweller(strength=10, outfit=SimpleNamespace(strength=5))]
    quest = _make_quest(_make_req(RequirementType.STAT, {"stat": "strength", "value": 15, "count": 1}))
    assert party_missing_requirements(party, quest) == []

    quest = _make_quest(_make_req(RequirementType.STAT, {"stat": "strength", "value": 16, "count": 1}))
    assert party_missing_requirements(party, quest) == ["Need a party dweller with Strength 16+"]


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_quest(async_client: AsyncClient, async_session: AsyncSession) -> None:
    """Test that eligible dwellers endpoint returns only dwellers meeting quest requirements.

    This is a TDD test - it will fail until the eligible dwellers endpoint is implemented.
    """
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Level Quest",
        short_description="Requires level 5",
        long_description="This quest requires a level 5 dweller",
        requirements="Level 5 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 5, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()

    dweller_low = Dweller(first_name="Low", gender="male", rarity="common", level=1, vault_id=vault.id)
    dweller_med = Dweller(first_name="Med", gender="male", rarity="common", level=5, vault_id=vault.id)
    dweller_high = Dweller(first_name="High", gender="male", rarity="common", level=10, vault_id=vault.id)
    async_session.add(dweller_low)
    async_session.add(dweller_med)
    async_session.add(dweller_high)
    await async_session.commit()
    await async_session.refresh(dweller_low)
    await async_session.refresh(dweller_med)
    await async_session.refresh(dweller_high)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert len(data) == 2, f"Expected 2 eligible dwellers, got {len(data)}"
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_med.id) in dweller_ids
    assert str(dweller_high.id) in dweller_ids
    assert str(dweller_low.id) not in dweller_ids


@pytest.mark.asyncio
async def test_get_available_quests_excludes_locked(async_client: AsyncClient, async_session: AsyncSession) -> None:
    """Test that available quests endpoint excludes locked chain quests."""
    from app.tests.factory.rooms import create_overseers_office
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    await async_session.commit()

    quest_a = Quest(
        title="Quest A",
        short_description="First quest",
        long_description="Complete quest A first",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest_a)
    await async_session.commit()
    await async_session.refresh(quest_a)

    quest_b = Quest(
        title="Quest B",
        short_description="Second quest",
        long_description="Requires quest A",
        requirements="Complete quest A",
        rewards="200 caps",
        quest_type="side",
        previous_quest_id=quest_a.id,
    )
    async_session.add(quest_b)
    await async_session.commit()
    await async_session.refresh(quest_b)

    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest_a.id, vault_id=vault.id)
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest_b.id, vault_id=vault.id)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/available",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    quest_titles = [q["title"] for q in data]
    assert "Quest A" in quest_titles, "Quest A should be available"
    assert "Quest B" not in quest_titles, "Quest B should be locked (previous not completed)"
