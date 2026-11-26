from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import RequirementType, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
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
from app.tests.factory.items import create_fake_outfit, create_fake_weapon
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.user import user_authentication_headers


def _make_req(requirement_type: RequirementType, requirement_data: dict, *, is_mandatory: bool = True) -> object:
    return SimpleNamespace(
        requirement_type=requirement_type, requirement_data=requirement_data, is_mandatory=is_mandatory
    )


def _make_quest(*reqs: object) -> object:
    return SimpleNamespace(title="Test Quest", quest_requirements=list(reqs))


def _req(spec: tuple) -> object:
    requirement_type, requirement_data, *mandatory = spec
    return _make_req(requirement_type, requirement_data, is_mandatory=mandatory[0] if mandatory else True)


def _party_dweller(**attrs: object) -> object:
    defaults: dict[str, object] = dict.fromkeys(
        ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"), 1
    )
    defaults |= {"level": 1, "weapon": None, "outfit": None, "visual_attributes": None}
    return SimpleNamespace(**(defaults | attrs))


async def _user_vault(async_session: AsyncSession):
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    return user_data, user, vault


async def _quest(
    async_session: AsyncSession,
    *,
    title: str = "Test Quest",
    requirements: tuple | list[tuple] = (),
    previous_quest_id=None,
    quest_type: str = "side",
) -> Quest:
    quest = Quest(
        title=title,
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type=quest_type,
        previous_quest_id=previous_quest_id,
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)
    for requirement_type, requirement_data, is_mandatory in requirements:
        async_session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=requirement_type,
                requirement_data=requirement_data,
                is_mandatory=is_mandatory,
            )
        )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])
    return quest


async def _add_dweller(async_session: AsyncSession, vault, first_name: str, *, level: int = 1, **attrs) -> Dweller:
    dweller = Dweller(first_name=first_name, gender="male", rarity="common", level=level, vault_id=vault.id, **attrs)
    async_session.add(dweller)
    return dweller


async def _eligible_ids(async_client: AsyncClient, user, user_data, vault, quest) -> list[str]:
    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.get(f"/quests/{vault.id}/{quest.id}/eligible-dwellers", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    return [dweller["id"] for dweller in response.json()]


@pytest.mark.parametrize("room_name", ["Living room", "Living Quarters"])
async def test_validate_room_requirement_accepts_living_quarters_alias(
    async_session: AsyncSession, room_name: str
) -> None:
    _, _, vault = await _user_vault(async_session)
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


async def test_validate_dweller_count_requirement_not_met(async_session: AsyncSession) -> None:
    _, _, vault = await _user_vault(async_session)
    for i in range(2):
        await _add_dweller(async_session, vault, f"Test{i}")
    await async_session.commit()
    assert await validate_dweller_count_requirement(async_session, vault.id, {"count": 5}) is False


async def test_validate_quest_completed_requirement_not_met(async_session: AsyncSession) -> None:
    _, _, vault = await _user_vault(async_session)
    prereq_quest = await _quest(async_session, title="Prerequisite Quest")
    assert await validate_quest_completed_requirement(async_session, vault.id, {"quest_id": prereq_quest.id}) is False


async def test_vault_missing_requirements(async_session: AsyncSession) -> None:
    _, _, vault = await _user_vault(async_session)
    quest = await _quest(async_session, requirements=[(RequirementType.LEVEL, {"level": 100, "count": 1}, True)])
    missing = await vault_missing_requirements(async_session, vault.id, quest)
    assert len(missing) > 0
    assert any("level" in desc.lower() for desc in missing)


async def test_vault_missing_requirements_empty(async_session: AsyncSession) -> None:
    _, _, vault = await _user_vault(async_session)
    quest = await _quest(async_session, title="No Requirements")
    assert await vault_missing_requirements(async_session, vault.id, quest) == []


async def test_vault_missing_requirements_omits_optional(async_session: AsyncSession) -> None:
    _, _, vault = await _user_vault(async_session)
    quest = await _quest(
        async_session, title="Optional Gate", requirements=[(RequirementType.LEVEL, {"level": 999, "count": 1}, False)]
    )
    assert await vault_missing_requirements(async_session, vault.id, quest) == []


async def test_vault_missing_requirements_unknown_type_fails_closed() -> None:
    quest = _make_quest(_make_req("bogus", {}))
    missing = await vault_missing_requirements(None, uuid4(), quest)
    assert missing == ["Unknown requirement: bogus"]


async def test_vault_missing_requirements_validator_error_fails_closed(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, vault = await _user_vault(async_session)
    quest = await _quest(
        async_session, title="Boom Quest", requirements=[(RequirementType.LEVEL, {"level": 100, "count": 1}, True)]
    )

    async def _boom(_db_session: object, _vault_id: object, requirement_data: dict) -> bool:
        raise RuntimeError("validator exploded")

    monkeypatch.setattr(requirements, "validate_level_requirement", _boom)
    missing = await vault_missing_requirements(async_session, vault.id, quest)
    assert missing == ["Need a dweller at level 100 or higher"]


async def test_vault_missing_requirements_checker_error_fails_closed(async_session: AsyncSession) -> None:
    # A non-numeric LEVEL threshold raises inside count_at_level against a persisted dweller, which is
    # exactly what the fail-closed wrapper has to absorb.
    _, _, vault = await _user_vault(async_session)
    quest = await _quest(async_session, title="Snapshot Boom Quest")
    await _add_dweller(async_session, vault, "Comparand")
    await async_session.commit()
    bad_data = {"level": "invalid", "count": 1}
    async_session.add(
        QuestRequirement(
            quest_id=quest.id, requirement_type=RequirementType.LEVEL, requirement_data=bad_data, is_mandatory=True
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_requirements"])
    missing = await vault_missing_requirements(async_session, vault.id, quest)
    assert missing == [requirements._describe_level(bad_data)]
    assert missing == ["Need a dweller at level invalid or higher"]


def test_individual_meets_requirement_ignores_count() -> None:
    dweller = _party_dweller(level=5)
    req = _make_req(RequirementType.LEVEL, {"level": 5, "count": 2})
    assert individual_meets_requirement(dweller, req) is True
    assert individual_meets_requirement(_party_dweller(level=4), req) is False
    # Vault-level and optional gates never disqualify an individual.
    flat = [
        _make_req(RequirementType.ROOM, {"room_type": "overseers_office"}),
        _make_req(RequirementType.ITEM, {"item_name": "Vault 33 suit"}),
        _make_req(RequirementType.LEVEL, {"level": 99, "count": 1}, is_mandatory=False),
    ]
    assert all(individual_meets_requirement(dweller, req) is True for req in flat)


LEVEL, ITEM, ATTACK, STAT = (
    RequirementType.LEVEL,
    RequirementType.ITEM,
    RequirementType.ATTACK,
    RequirementType.STAT,
)
PARTY_GATE_CASES = [
    (
        "level",
        [(LEVEL, {"level": 5, "count": 2}), (LEVEL, {"level": 99}, False)],
        [_party_dweller(level=5), _party_dweller(level=6)],
        [],
    ),
    (
        "level-short",
        [(LEVEL, {"level": 7, "count": 1})],
        [_party_dweller(level=5), _party_dweller(level=6)],
        ["Need a dweller at level 7 or higher"],
    ),
    # Item gates are vault-wide, so a party never fails on the item it will carry.
    (
        "item-ignored",
        [(ITEM, {"item_name": "10mm Pistol", "count": 1})],
        [_party_dweller(weapon=SimpleNamespace(name="10mm Pistol"))],
        [],
    ),
    (
        "attack",
        [(ATTACK, {"attack": 20, "count": 1})],
        [_party_dweller(weapon=SimpleNamespace(name="Rifle", damage_min=10, damage_max=30))],
        [],
    ),
    (
        "attack-short",
        [(ATTACK, {"attack": 21, "count": 1})],
        [_party_dweller(weapon=SimpleNamespace(name="Rifle", damage_min=10, damage_max=30))],
        ["Need a party dweller with 21+ attack"],
    ),
    (
        "stat",
        [(STAT, {"stat": "strength", "value": 15, "count": 1})],
        [_party_dweller(strength=10, outfit=SimpleNamespace(strength=5))],
        [],
    ),
    (
        "stat-short",
        [(STAT, {"stat": "strength", "value": 16, "count": 1})],
        [_party_dweller(strength=10, outfit=SimpleNamespace(strength=5))],
        ["Need a party dweller with Strength 16+"],
    ),
]


@pytest.mark.parametrize(
    ("requirements", "party", "expected"), [case[1:] for case in PARTY_GATE_CASES], ids=[c[0] for c in PARTY_GATE_CASES]
)
def test_party_missing_requirements_gate_table(requirements, party, expected) -> None:
    assert party_missing_requirements(party, _make_quest(*map(_req, requirements))) == expected


# Roster rows are (name, dweller fields, gear); gear is ("weapon"|"outfit", fields).
RIFLE, WEAK_BLADE = ("weapon", {"damage_min": 10, "damage_max": 30}), ("weapon", {"damage_min": 1, "damage_max": 3})
ELIGIBLE_CASES = [
    (
        "level",
        (LEVEL, {"level": 5, "count": 1}),
        [("Low", {"level": 1}, None), ("Med", {"level": 5}, None), ("High", {"level": 10}, None)],
        ("Med", "High"),
    ),
    # Eligibility is per-individual: a count-2 gate still lists each qualifying dweller.
    (
        "count-two",
        (LEVEL, {"level": 5, "count": 2}),
        [("A", {"level": 5}, None), ("B", {"level": 6}, None), ("Low", {"level": 1}, None)],
        ("A", "B"),
    ),
    # A STAT gate must agree with the start path's party policy instead of returning an empty list.
    (
        "stat",
        (STAT, {"stat": "strength", "value": 10, "count": 1}),
        [("Strong", {"strength": 10}, None), ("Weak", {"strength": 5}, None)],
        ("Strong",),
    ),
    # Exercises the eager-loaded Dweller.outfit path feeding effective_stat.
    (
        "outfit-bonus",
        (STAT, {"stat": "strength", "value": 10, "count": 1}),
        [("Buffed", {"strength": 8}, ("outfit", {"strength": 2})), ("Weak", {"strength": 8}, None)],
        ("Buffed",),
    ),
    (
        "item-ignored",
        (ITEM, {"item_name": "Laser Pistol", "count": 1}),
        [("Armed", {}, ("weapon", {"name": "Laser Pistol"})), ("Unarmed", {}, None)],
        ("Armed", "Unarmed"),
    ),
    ("attack", (ATTACK, {"attack": 15, "count": 1}), [("Strong", {}, RIFLE), ("Weak", {}, WEAK_BLADE)], ("Strong",)),
]


@pytest.mark.parametrize(
    ("requirement", "roster", "expected"),
    [case[1:] for case in ELIGIBLE_CASES],
    ids=[case[0] for case in ELIGIBLE_CASES],
)
async def test_get_eligible_dwellers_applies_the_personal_gates(
    async_client: AsyncClient, async_session: AsyncSession, requirement, roster, expected
) -> None:
    user_data, user, vault = await _user_vault(async_session)
    quest = await _quest(async_session, title="Gate Quest", requirements=[(*requirement, True)])
    created = {name: await _add_dweller(async_session, vault, name, **fields) for name, fields, _gear in roster}
    await async_session.commit()
    for name, _fields, gear in roster:
        if gear is None:
            continue
        kind, attributes = gear
        crud_model, payload = (
            (crud.weapon, create_fake_weapon()) if kind == "weapon" else (crud.outfit, create_fake_outfit())
        )
        await crud_model.create(async_session, obj_in=payload | attributes | {"dweller_id": created[name].id})

    dweller_ids = await _eligible_ids(async_client, user, user_data, vault, quest)

    assert set(dweller_ids) == {str(created[name].id) for name in expected}


async def test_get_available_quests_excludes_locked(async_client: AsyncClient, async_session: AsyncSession) -> None:
    user_data, user, vault = await _user_vault(async_session)
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    quest_a = await _quest(async_session, title="Quest A")
    quest_b = await _quest(async_session, title="Quest B", previous_quest_id=quest_a.id)
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest_a.id, vault_id=vault.id)
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest_b.id, vault_id=vault.id)
    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.get(f"/quests/{vault.id}/available", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    quest_titles = [q["title"] for q in response.json()]
    assert "Quest A" in quest_titles, "Quest A should be available"
    assert "Quest B" not in quest_titles, "Quest B should be locked (previous not completed)"
