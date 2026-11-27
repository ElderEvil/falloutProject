import pytest
from sqlalchemy import func, select

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, ObjectiveCategoryEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.dweller import DwellerCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.room import RoomCreate
from app.services.exploration_service import exploration_service
from app.services.progression.objectives.guidance import create_objective_for_vault, current_state_progress
from app.tests.test_services._transaction_helpers import fail_sql

ROOM = {
    "category": RoomTypeEnum.PRODUCTION,
    "base_cost": 100,
    "t2_upgrade_cost": None,
    "t3_upgrade_cost": None,
    "size_min": 3,
    "size_max": 3,
}
DWELLER = {
    "first_name": "Staffed",
    "gender": GenderEnum.MALE,
    "rarity": RarityEnum.COMMON,
    "age_group": AgeGroupEnum.ADULT,
    "level": 1,
    "max_health": 100,
    "health": 100,
}


async def _room(db, vault, ability, name="Power Generator", capacity=None, size=None):
    obj_in = RoomCreate(name=name, ability=ability, capacity=capacity, size=size, vault_id=vault.id, **ROOM)
    return await crud.room.create(db_session=db, obj_in=obj_in)


async def _dweller(db, vault, room_id=None, **stats):
    dweller = await crud.dweller.create(db_session=db, obj_in=DwellerCreate(vault_id=vault.id, **{**DWELLER, **stats}))
    if room_id is not None:
        dweller.room_id = room_id
        db.add(dweller)
        await db.commit()
    return dweller


def _objective(objective_type, target_entity=None, amount=1, challenge="Objective", reward="50 caps"):
    return Objective(
        challenge=challenge,
        reward=reward,
        category="starter",
        objective_type=objective_type,
        target_entity=target_entity or {},
        target_amount=amount,
    )


@pytest.mark.parametrize(("staffed", "expected"), [(True, 1), (False, 0)], ids=["staffed", "unstaffed"])
async def test_assign_correct_credits_only_correct_staffing(async_session, vault, staffed, expected):
    room = await _room(async_session, vault, SPECIALEnum.STRENGTH)
    if staffed:
        await _dweller(async_session, vault, room.id, strength=8, agility=2)
        await _dweller(async_session, vault, room.id, strength=2, agility=8)

    objective = _objective("assign_correct", challenge="Assign a dweller correctly")
    assert await current_state_progress(async_session, vault.id, objective) == expected


async def test_build_additional_housing_credits_construction_not_upgrades(async_session, vault):
    seeded = await _room(async_session, vault, SPECIALEnum.CHARISMA, name="Living room", capacity=8, size=3)
    objective = _objective(
        "build",
        {"room_type": "living_room", "additional": True, "baseline_size": 3},
        challenge="Build a Living Quarters",
        reward="dweller:Wanderer",
    )
    assert await current_state_progress(async_session, vault.id, objective) == 0

    seeded.capacity = 10
    seeded.tier = 2
    async_session.add(seeded)
    await async_session.commit()

    assert await current_state_progress(async_session, vault.id, objective) == 0

    await _room(async_session, vault, SPECIALEnum.CHARISMA, name="Living room", capacity=8, size=3)

    assert await current_state_progress(async_session, vault.id, objective) == 1


async def test_explore_credits_an_existing_run_but_not_quest_completion(async_session, vault):
    dweller = await _dweller(async_session, vault, first_name="Explorer")
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    explore = _objective("explore", challenge="Send a dweller exploring")
    expedition = _objective("expedition", amount=3, challenge="Complete 3 Quests", reward="300 caps")
    assert await current_state_progress(async_session, vault.id, explore) == 1
    assert await current_state_progress(async_session, vault.id, expedition) == 0


def _inserts_objective_link(statement: str) -> bool:
    return statement.lower().startswith("insert into vaultobjectiveprogresslink")


async def test_create_objective_rolls_back_template_when_link_insert_fails(async_session, vault):
    links_before = (
        await async_session.execute(select(func.count()).select_from(VaultObjectiveProgressLink))
    ).scalar_one()
    objective_data = ObjectiveCreate(
        challenge="Rollback Objective",
        reward="50 caps",
        category=ObjectiveCategoryEnum.DAILY,
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=3,
    )

    async with fail_sql(async_session, _inserts_objective_link, "injected link failure"):
        with pytest.raises(RuntimeError, match="injected link failure"):
            await create_objective_for_vault(async_session, vault.id, objective_data)

    await async_session.rollback()
    templates = (
        await async_session.execute(
            select(func.count()).select_from(Objective).where(Objective.challenge == "Rollback Objective")
        )
    ).scalar_one()
    links_after = (
        await async_session.execute(select(func.count()).select_from(VaultObjectiveProgressLink))
    ).scalar_one()
    assert templates == 0
    assert links_after == links_before
