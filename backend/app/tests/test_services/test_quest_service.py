from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import QuestType, RequirementType
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services import quest_service as facade
from app.services.progression.quests import availability
from app.services.progression.quests import service as canonical
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.items import create_fake_outfit, create_fake_weapon
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.user import user_authentication_headers
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.utils.quest_duration import effective_quest_duration_minutes
from app.utils.time import utcnow


async def _vault(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


async def _vault_with_office(async_session: AsyncSession, tier: int = 1):
    vault = await _vault(async_session)
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


async def _gated_quest(
    async_session: AsyncSession, vault, title: str, *requirements: tuple, assign: bool = True
) -> Quest:
    quest = await _create_quest(async_session, title=title)
    for requirement_type, requirement_data in requirements:
        async_session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=requirement_type,
                requirement_data=requirement_data,
                is_mandatory=True,
            )
        )
    await async_session.commit()
    if assign:
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    return quest


async def _add_dweller(async_session: AsyncSession, vault, **overrides) -> Dweller:
    dweller = Dweller(**(create_fake_adult_dweller() | overrides), vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _equip_weapon(async_session: AsyncSession, dweller, name: str | None = None, **fields) -> None:
    data = create_fake_weapon() | {"dweller_id": dweller.id} | fields
    if name is not None:
        data["name"] = name
    await crud.weapon.create(async_session, obj_in=data)


async def _wear_outfit(async_session: AsyncSession, dweller, name: str) -> None:
    await crud.outfit.create(async_session, obj_in=create_fake_outfit() | {"name": name, "dweller_id": dweller.id})


async def _vault_with_level_dweller(async_session: AsyncSession, level: int, *, office: bool = True):
    vault = await (_vault_with_office(async_session) if office else _vault(async_session))
    await _add_dweller(async_session, vault, level=level)
    return vault


async def _read_quest(async_session: AsyncSession, vault, quest: Quest):
    reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    return next(q for q in reads if q.id == quest.id)


async def _auth(async_client, user, user_data) -> dict:
    return await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])


async def _start_party(async_session: AsyncSession, quest, vault, *dwellers):
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [d.id for d in dwellers])
    return await quest_service.start_quest(async_session, quest.id, vault.id)


async def _party(async_session: AsyncSession, title: str, requirement: tuple, **dweller_fields):
    vault = await _vault_with_office(async_session)
    quest = await _gated_quest(async_session, vault, title, requirement)
    dweller = await _add_dweller(async_session, vault, **dweller_fields)
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    return vault, quest, dweller


async def test_requirement_gated_quest_reads_as_locked_and_start_rejects(async_client, async_session) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    quest = await _gated_quest(async_session, vault, "Population Gate", (RequirementType.DWELLER_COUNT, {"count": 100}))
    headers = await _auth(async_client, user, user_data)
    read_response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert read_response.status_code == 200, f"Expected 200, got {read_response.status_code}: {read_response.text}"
    quest_read = next(q for q in read_response.json() if q["id"] == str(quest.id))
    assert quest_read["is_locked"] is True
    assert quest_read["is_visible"] is True
    assert "dwellers" in quest_read["lock_reason"]
    start_response = await async_client.post(f"/quests/{vault.id}/{quest.id}/start", headers=headers)
    assert start_response.status_code == 400, f"Expected 400, got {start_response.status_code}: {start_response.text}"
    assert "dwellers" in start_response.json()["detail"]


async def test_chain_gate_blocks_availability_and_read_until_the_predecessor_completes(
    async_session: AsyncSession,
) -> None:
    vault = await _vault_with_office(async_session)
    starter = await _create_quest(async_session, title="Getting Started")
    follow_up = await _create_quest(async_session, title="Next Steps", previous_quest_id=starter.id)
    await crud.quest_crud.assign_to_vault(async_session, follow_up.id, vault.id, is_visible=True)

    verdict = await quest_service.get_quest_availability(async_session, vault.id, follow_up)
    assert (verdict.available, verdict.lock_reason) == (False, "Complete 'Getting Started' first")
    read = await _read_quest(async_session, vault, follow_up)
    assert (read.is_locked, read.lock_reason) == (True, "Complete 'Getting Started' first")

    await crud.quest_crud.assign_to_vault(async_session, starter.id, vault.id, is_visible=True)
    link = await crud.quest_crud.get_link(async_session, quest_id=starter.id, vault_id=vault.id)
    link.is_completed = True
    await async_session.commit()
    assert (await quest_service.get_quest_availability(async_session, vault.id, follow_up)).available is True
    assert (await _read_quest(async_session, vault, follow_up)).is_locked is False


# Availability answers on two surfaces for one quest: the verdict and the vault read.
# (id, dweller level, gate, office, read visible, read locked, read reason, available, verdict reason)
AVAILABILITY_CASES = [
    ("open", 1, None, True, True, False, None, True, None),
    ("no-office", 1, None, False, True, True, availability.OFFICE_LOCK_REASON, False, availability.OFFICE_LOCK_REASON),
    (
        "population-gate",
        1,
        (RequirementType.DWELLER_COUNT, {"count": 100}),
        True,
        True,
        True,
        "dwellers",
        False,
        "dwellers",
    ),
    ("level-near", 20, (RequirementType.LEVEL, {"level": 30}), True, True, True, "level", False, "level"),
    ("level-beyond-reveal", 20, (RequirementType.LEVEL, {"level": 46}), True, False, None, None, False, "level"),
    ("level-met", 46, (RequirementType.LEVEL, {"level": 46}), True, True, False, None, True, None),
]


@pytest.mark.parametrize(
    ("level", "gate", "office", "visible", "locked", "read_reason", "available", "verdict_reason"),
    [row[1:] for row in AVAILABILITY_CASES],
    ids=[row[0] for row in AVAILABILITY_CASES],
)
async def test_quest_availability_and_read_agree(
    async_session: AsyncSession, level, gate, office, visible, locked, read_reason, available, verdict_reason
) -> None:
    vault = await (_vault_with_office(async_session) if office else _vault(async_session))
    await _add_dweller(async_session, vault, level=level)
    quest = await _gated_quest(async_session, vault, "Availability Quest", *((gate,) if gate else ()))

    verdict = await quest_service.get_quest_availability(async_session, vault.id, quest)
    assert verdict.available is available
    if available:
        assert (verdict.lock_reason, verdict.missing) == (None, [])
    elif verdict_reason == availability.OFFICE_LOCK_REASON:
        assert verdict.lock_reason == availability.OFFICE_LOCK_REASON
    else:
        assert verdict_reason in verdict.lock_reason
        if gate[0] is RequirementType.DWELLER_COUNT:
            assert any("dwellers" in missing for missing in verdict.missing)

    reads = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100)
    quest_read = next((q for q in reads if q.id == quest.id), None)
    assert (quest_read is not None) is visible
    if visible:
        assert (quest_read.is_locked, quest_read.is_visible) == (locked, True)
        if read_reason:
            assert read_reason in quest_read.lock_reason


async def test_available_only_respects_level_reveal(async_session: AsyncSession) -> None:
    vault = await _vault_with_level_dweller(async_session, level=20)
    hidden = await _gated_quest(async_session, vault, "Hidden Level 46", (RequirementType.LEVEL, {"level": 46}))
    open_quest = await _create_quest(async_session, title="Open Quest")
    await crud.quest_crud.assign_to_vault(async_session, open_quest.id, vault.id, is_visible=True)
    page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 100, available_only=True)
    assert all(q.id != hidden.id for q in page)
    assert {q.title for q in page} == {"Open Quest"}


async def test_level_gated_quest_shown_locked_without_office(async_session: AsyncSession) -> None:
    vault = await _vault_with_level_dweller(async_session, level=20, office=False)
    quest = await _gated_quest(async_session, vault, "No Office Level 46", (RequirementType.LEVEL, {"level": 46}))
    quest_read = await _read_quest(async_session, vault, quest)
    assert (quest_read.is_locked, quest_read.lock_reason) == (True, "Requires Overseer's Office")


async def test_normal_read_fills_page_past_hidden_quests(async_session: AsyncSession) -> None:
    vault = await _vault_with_level_dweller(async_session, level=20)
    hidden = await _gated_quest(async_session, vault, "Hidden Level 46", (RequirementType.LEVEL, {"level": 46}))
    open_quests = [await _create_quest(async_session, title=f"Open {i}") for i in range(4)]
    for quest in open_quests:
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    page = await quest_service.get_quests_for_vault(async_session, vault.id, 0, 3)
    assert len(page) == 3
    assert all(q.id != hidden.id for q in page)
    assert {q.title for q in page} <= {"Open 0", "Open 1", "Open 2", "Open 3"}


# Quest gates are read (locked + reason) and enforced (start refuses or departs). Each row keeps
# both verdicts for one gate so the read path and the start path cannot drift apart.
# (id, gates, roster, gear, party, read lock reason, start error); gear rows are (dweller index, kind, fields).
GATE_CASES = [
    ("level-short", [(RequirementType.LEVEL, {"level": 46})], [{"level": 40}], [], (0,), "level", "level 46"),
    ("level-met", [(RequirementType.LEVEL, {"level": 46})], [{"level": 40}, {"level": 46}], [], (0, 1), None, None),
    (
        "item-missing",
        [(RequirementType.ITEM, {"item_name": "Laser Pistol"})],
        [{}],
        [],
        (0,),
        "Laser Pistol",
        "Laser Pistol",
    ),
    (
        "item-equipped",
        [(RequirementType.ITEM, {"item_name": "Laser Pistol"})],
        [{}],
        [(0, "weapon", {"name": "Laser Pistol"})],
        (0,),
        None,
        None,
    ),
    # The read path counts gear worn by any vault dweller, so the start path must agree.
    (
        "item-worn-by-other-dweller",
        [(RequirementType.ITEM, {"item_name": "Vault 33 suit"})],
        [{}, {}],
        [(1, "outfit", {"name": "Vault 33 suit"})],
        (0,),
        None,
        None,
    ),
    (
        "item-worn-by-dead-dweller",
        [(RequirementType.ITEM, {"item_name": "Vault 33 suit"})],
        [{}, {"is_dead": True}],
        [(1, "outfit", {"name": "Vault 33 suit"})],
        (0,),
        "Vault 33 suit",
        "Vault 33 suit",
    ),
    (
        "item-case-insensitive",
        [(RequirementType.ITEM, {"item_name": "Vault 33 suit"})],
        [{}, {}],
        [(1, "outfit", {"name": "vault 33 SUIT"})],
        (0,),
        None,
        None,
    ),
    (
        "attack-short",
        [(RequirementType.ATTACK, {"attack": 20})],
        [{}],
        [(0, "weapon", {"damage_min": 5, "damage_max": 10})],
        (0,),
        "attack",
        "20",
    ),
    (
        "attack-met",
        [(RequirementType.ATTACK, {"attack": 20})],
        [{}],
        [(0, "weapon", {"damage_min": 15, "damage_max": 25})],
        (0,),
        None,
        None,
    ),
    (
        "stat-short",
        [(RequirementType.STAT, {"stat": "strength", "value": 6})],
        [{"strength": 3}],
        [],
        (0,),
        "Strength",
        "Strength",
    ),
    ("stat-met", [(RequirementType.STAT, {"stat": "strength", "value": 6})], [{"strength": 6}], [], (0,), None, None),
]


@pytest.mark.parametrize(
    ("gates", "roster", "gear", "party", "reason", "start_error"),
    [row[1:] for row in GATE_CASES],
    ids=[row[0] for row in GATE_CASES],
)
async def test_requirement_gate_read_and_start_agree(
    async_session: AsyncSession, gates, roster, gear, party, reason, start_error
) -> None:
    vault = await _vault_with_office(async_session)
    quest = await _gated_quest(async_session, vault, "Gate Quest", *gates)
    dwellers = [await _add_dweller(async_session, vault, **fields) for fields in roster]
    for index, kind, fields in gear:
        model, payload = (
            (crud.weapon, create_fake_weapon()) if kind == "weapon" else (crud.outfit, create_fake_outfit())
        )
        await model.create(async_session, obj_in=payload | fields | {"dweller_id": dwellers[index].id})
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dwellers[i].id for i in party])

    read = await _read_quest(async_session, vault, quest)
    assert (read.is_locked, read.is_visible) == (reason is not None, True)
    if reason is not None:
        assert reason in read.lock_reason
    if start_error is None:
        assert (await quest_service.start_quest(async_session, quest.id, vault.id)).started_at is not None
    else:
        with pytest.raises(ValidationException, match=start_error):
            await quest_service.start_quest(async_session, quest.id, vault.id)


def test_quest_service_facade_reexports_canonical_surface() -> None:
    for name in ("QuestAvailability", "OFFICE_ROOM_TYPE", "OFFICE_LOCK_REASON", "CHAIN_LOCK_REASON", "REVEAL_MARGIN"):
        assert getattr(facade, name) is getattr(availability, name)
    assert facade.QuestService is canonical.QuestService
    assert facade.quest_service is canonical.quest_service


async def test_item_requirement_read_and_start_agree_for_non_party_wearer(async_client, async_session) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    quest = await _gated_quest(
        async_session, vault, "Non-Party Wearer Agreement", (RequirementType.ITEM, {"item_name": "Vault 33 suit"})
    )
    await _wear_outfit(async_session, await _add_dweller(async_session, vault), "Vault 33 suit")
    party_member = await _add_dweller(async_session, vault)
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [party_member.id])
    headers = await _auth(async_client, user, user_data)
    read_response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert read_response.status_code == 200, f"Expected 200, got {read_response.status_code}: {read_response.text}"
    quest_read = next(q for q in read_response.json() if q["id"] == str(quest.id))
    assert quest_read["is_locked"] is False
    # Per-row verdicts ride along on the read, so the UI can show which gate blocks what.
    item_row = next(r for r in quest_read["quest_requirements"] if r["requirement_type"] == "item")
    assert item_row["is_met"] is True
    start_response = await async_client.post(f"/quests/{vault.id}/{quest.id}/start", headers=headers)
    assert start_response.status_code == 200, f"Expected 200, got {start_response.status_code}: {start_response.text}"


@pytest.mark.parametrize("running_count", [2, 3])
async def test_timed_quest_limit_counts_outbound_and_returning_only(async_session: AsyncSession, running_count: int):
    vault = await _vault_with_office(async_session, tier=3)
    other_vault = await _vault_with_office(async_session, tier=3)
    now = utcnow()
    first_quest_id = None
    for index in range(running_count + 3):
        quest = await _create_quest(async_session, title=f"Existing {index}")
        quest.quest_category = "training" if index == running_count + 2 else "combat"
        if index == 0:
            first_quest_id = quest.id
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
            VaultQuestCompletionLink(quest_id=quest.id, vault_id=other_vault.id, started_at=now, duration_minutes=60)
        )
        await async_session.commit()
    candidate = await _create_quest(async_session, title="Next timed quest")
    await crud.quest_crud.assign_to_vault(async_session, candidate.id, vault.id, is_visible=True)
    await team_service.assign_quest_team(
        async_session, candidate.id, vault.id, [(await _add_dweller(async_session, vault)).id]
    )
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


@pytest.mark.parametrize("office_tier", [1, 2, 3])
async def test_quest_slots_follow_office_tier(async_session: AsyncSession, office_tier: int) -> None:
    vault = await _vault_with_office(async_session, tier=office_tier)
    first_link = None
    for index in range(office_tier):
        quest = await _create_quest(async_session, title=f"Tier quest {index}")
        await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
        dweller = await _add_dweller(async_session, vault)
        await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
        link = await quest_service.start_quest(async_session, quest.id, vault.id)
        first_link = first_link or link
    assert first_link is not None
    assert first_link.duration_minutes == effective_quest_duration_minutes(60, office_tier=office_tier)
    overflow = await _create_quest(async_session, title="One too many")
    await crud.quest_crud.assign_to_vault(async_session, overflow.id, vault.id, is_visible=True)
    await team_service.assign_quest_team(
        async_session, overflow.id, vault.id, [(await _add_dweller(async_session, vault)).id]
    )
    with pytest.raises(ResourceConflictException, match=f"All {office_tier} quest slots"):
        await quest_service.start_quest(async_session, overflow.id, vault.id)


async def test_unsettled_quest_stays_listed_after_its_prerequisite_is_lost(async_session: AsyncSession) -> None:
    vault = await _vault_with_office(async_session)
    quest = await _gated_quest(async_session, vault, "Gear Gate", (RequirementType.ITEM, {"item_name": "Tuning fork"}))
    link = await crud.quest_crud.get_link(async_session, quest_id=quest.id, vault_id=vault.id)
    link.started_at = utcnow()
    link.duration_minutes = 60
    await async_session.commit()
    read = await _read_quest(async_session, vault, quest)
    assert (read.is_visible, read.is_locked, read.started_at is not None) == (True, False, True)
    ready_link = await crud.quest_crud.get_link_for_update(async_session, quest_id=quest.id, vault_id=vault.id)
    assert ready_link is not None
    ready_link.started_at = None
    ready_link.is_reward_ready = True
    await async_session.commit()
    read = await _read_quest(async_session, vault, quest)
    assert (read.is_visible, read.is_locked, read.is_reward_ready) == (True, False, True)


async def test_assign_rejects_scheduler_owned_quest_types(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    for quest_type in ("daily", "repeatable", "event"):
        quest = await crud.quest_crud.create(
            async_session,
            obj_in=QuestCreate(
                title=f"Scheduled {quest_type}",
                short_description="Scheduler-owned quest",
                long_description="Visibility is owned by the scheduler, not the assign endpoint.",
                requirements="No prerequisites",
                rewards="10 caps",
                quest_type=quest_type,
            ),
        )
        with pytest.raises(ValidationException, match="managed by the scheduler"):
            await quest_service.assign_quest_to_vault(db_session=async_session, quest_id=quest.id, vault_id=vault.id)


@pytest.mark.parametrize(
    ("visible", "error", "message"),
    [
        (None, ResourceNotFoundException, "VaultQuestCompletionLink"),
        (False, AccessDeniedException, "not currently offered"),
    ],
    ids=["missing-link", "hidden-link"],
)
async def test_start_checks_offer_before_requirements(async_session: AsyncSession, visible, error, message):
    vault = await _vault_with_office(async_session)
    quest = await _gated_quest(async_session, vault, "Level gate", (RequirementType.LEVEL, {"level": 50}), assign=False)
    quest.quest_type = QuestType.DAILY
    if visible is not None:
        async_session.add(VaultQuestCompletionLink(vault_id=vault.id, quest_id=quest.id, is_visible=visible))
    await async_session.commit()
    with pytest.raises(error, match=message):
        await quest_service.start_quest_for_vault(async_session, vault.id, quest.id)


async def test_failed_arrival_candidate_does_not_abort_the_sweep(async_session: AsyncSession, caplog):
    vault = await _vault_with_office(async_session)
    broken = await _create_quest(async_session, title="Never started")
    good = await _create_quest(async_session, title="Arrived party")
    vault_id, good_id = vault.id, good.id
    arrived_at = utcnow() - timedelta(hours=2)
    async_session.add_all(
        [
            VaultQuestCompletionLink(vault_id=vault_id, quest_id=broken.id, return_completes_at=arrived_at),
            VaultQuestCompletionLink(
                vault_id=vault_id,
                quest_id=good_id,
                started_at=arrived_at,
                return_started_at=arrived_at,
                return_completes_at=arrived_at,
                duration_minutes=60,
            ),
        ]
    )
    await async_session.commit()
    assert await quest_service.check_and_complete_quests(async_session, vault_id=vault_id) == 1
    assert "Quest must be started before it can be completed" in caplog.text
    ready = await crud.quest_crud.get_link(async_session, quest_id=good_id, vault_id=vault_id)
    assert (ready is not None, ready.is_reward_ready) == (True, True)
