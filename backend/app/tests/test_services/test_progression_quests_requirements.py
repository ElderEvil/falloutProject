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
    individual_meets_requirement,
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


def test_individual_meets_requirement_ignores_count() -> None:
    """A candidate meeting a gate's threshold qualifies regardless of the aggregate count."""
    dweller = _party_dweller(level=5)
    req = _make_req(RequirementType.LEVEL, {"level": 5, "count": 2})
    assert individual_meets_requirement(dweller, req) is True

    # Below-threshold candidate fails the gate.
    assert individual_meets_requirement(_party_dweller(level=4), req) is False

    # Vault-level and optional gates never disqualify an individual.
    assert (
        individual_meets_requirement(dweller, _make_req(RequirementType.ROOM, {"room_type": "overseers_office"}))
        is True
    )
    assert (
        individual_meets_requirement(
            dweller, _make_req(RequirementType.LEVEL, {"level": 99, "count": 1}, is_mandatory=False)
        )
        is True
    )


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
async def test_get_eligible_dwellers_for_stat_requirement(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """A mandatory STAT requirement filters candidates by effective SPECIAL (regression).

    The eligible-dwellers endpoint must agree with the start path's party policy: a
    STAT-gated quest returns qualifying dwellers instead of an empty list.
    """
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Strength Quest",
        short_description="Requires strength 10",
        long_description="This quest requires a dweller with strength 10",
        requirements="Strength 10 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.STAT,
            requirement_data={"stat": "strength", "value": 10, "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    dweller_strong = Dweller(
        first_name="Strong", gender="male", rarity="common", level=1, vault_id=vault.id, strength=10
    )
    dweller_weak = Dweller(first_name="Weak", gender="male", rarity="common", level=1, vault_id=vault.id, strength=5)
    async_session.add(dweller_strong)
    async_session.add(dweller_weak)
    await async_session.commit()
    await async_session.refresh(dweller_strong)
    await async_session.refresh(dweller_weak)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_strong.id) in dweller_ids
    assert str(dweller_weak.id) not in dweller_ids


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_count_two_requirement(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """A count: 2 gate lists every qualifying candidate, not none (regression).

    Eligibility is per-individual: two dwellers who each meet the LEVEL threshold
    are both listed even though a valid party needs two of them.
    """
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Two Dwellers Quest",
        short_description="Requires two level 5 dwellers",
        long_description="This quest requires two level 5 dwellers",
        requirements="Two level 5 dwellers",
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
            requirement_data={"level": 5, "count": 2},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    dweller_a = Dweller(first_name="A", gender="male", rarity="common", level=5, vault_id=vault.id)
    dweller_b = Dweller(first_name="B", gender="male", rarity="common", level=6, vault_id=vault.id)
    dweller_low = Dweller(first_name="Low", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller_a)
    async_session.add(dweller_b)
    async_session.add(dweller_low)
    await async_session.commit()
    await async_session.refresh(dweller_a)
    await async_session.refresh(dweller_b)
    await async_session.refresh(dweller_low)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_a.id) in dweller_ids
    assert str(dweller_b.id) in dweller_ids
    assert str(dweller_low.id) not in dweller_ids


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_item_requirement(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """An ITEM gate is met by a dweller with the matching equipped weapon.

    Exercises the eager-loaded ``Dweller.weapon`` path in the eligible-dwellers query.
    """
    from app.tests.factory.items import create_fake_weapon
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Laser Pistol Quest",
        short_description="Requires a Laser Pistol",
        long_description="This quest requires a dweller equipped with a Laser Pistol",
        requirements="Laser Pistol",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ITEM,
            requirement_data={"item_name": "Laser Pistol", "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    dweller_armed = Dweller(first_name="Armed", gender="male", rarity="common", level=1, vault_id=vault.id)
    dweller_unarmed = Dweller(first_name="Unarmed", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller_armed)
    async_session.add(dweller_unarmed)
    await async_session.commit()
    await async_session.refresh(dweller_armed)
    await async_session.refresh(dweller_unarmed)

    weapon_data = create_fake_weapon()
    weapon_data["name"] = "Laser Pistol"
    weapon_data["dweller_id"] = dweller_armed.id
    await crud.weapon.create(async_session, obj_in=weapon_data)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_armed.id) in dweller_ids
    assert str(dweller_unarmed.id) not in dweller_ids


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_attack_requirement(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """An ATTACK gate uses the equipped weapon's average damage on the candidate."""
    from app.tests.factory.items import create_fake_weapon
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Attack Quest",
        short_description="Requires 15+ attack",
        long_description="This quest requires a dweller with 15+ attack",
        requirements="15+ attack",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.ATTACK,
            requirement_data={"attack": 15, "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    dweller_strong = Dweller(first_name="Strong", gender="male", rarity="common", level=1, vault_id=vault.id)
    dweller_weak = Dweller(first_name="Weak", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller_strong)
    async_session.add(dweller_weak)
    await async_session.commit()
    await async_session.refresh(dweller_strong)
    await async_session.refresh(dweller_weak)

    strong_weapon = create_fake_weapon()
    strong_weapon.update(damage_min=10, damage_max=30, dweller_id=dweller_strong.id)  # avg 20 >= 15
    await crud.weapon.create(async_session, obj_in=strong_weapon)
    weak_weapon = create_fake_weapon()
    weak_weapon.update(damage_min=1, damage_max=3, dweller_id=dweller_weak.id)  # avg 2 < 15
    await crud.weapon.create(async_session, obj_in=weak_weapon)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_strong.id) in dweller_ids
    assert str(dweller_weak.id) not in dweller_ids


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_outfit_bonus_stat_requirement(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """A STAT threshold met only through an outfit bonus still qualifies a candidate.

    Exercises the eager-loaded ``Dweller.outfit`` path feeding ``effective_stat``.
    """
    from app.tests.factory.items import create_fake_outfit
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Strength Quest",
        short_description="Requires strength 10",
        long_description="This quest requires a dweller with strength 10",
        requirements="Strength 10 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    async_session.add(
        QuestRequirement(
            quest_id=quest.id,
            requirement_type=RequirementType.STAT,
            requirement_data={"stat": "strength", "value": 10, "count": 1},
            is_mandatory=True,
        )
    )
    await async_session.commit()

    dweller_buffed = Dweller(
        first_name="Buffed", gender="male", rarity="common", level=1, vault_id=vault.id, strength=8
    )
    dweller_weak = Dweller(first_name="Weak", gender="male", rarity="common", level=1, vault_id=vault.id, strength=8)
    async_session.add(dweller_buffed)
    async_session.add(dweller_weak)
    await async_session.commit()
    await async_session.refresh(dweller_buffed)
    await async_session.refresh(dweller_weak)

    outfit_data = create_fake_outfit()
    outfit_data.update(strength=2, dweller_id=dweller_buffed.id)  # 8 + 2 = 10 effective
    await crud.outfit.create(async_session, obj_in=outfit_data)

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_buffed.id) in dweller_ids
    assert str(dweller_weak.id) not in dweller_ids


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
