"""Existing correct staffing must count toward a guided assign_correct step."""

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.objective import Objective
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.exploration_service import exploration_service
from app.services.progression.objectives.guidance import current_state_progress


async def _room(async_session, vault, ability, name="Power Generator", capacity=None, size=None):
    return await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
            name=name,
            category=RoomTypeEnum.PRODUCTION,
            ability=ability,
            base_cost=100,
            t2_upgrade_cost=None,
            t3_upgrade_cost=None,
            size_min=3,
            size_max=3,
            capacity=capacity,
            size=size,
            vault_id=vault.id,
        ),
    )


async def _dweller(async_session, vault, room_id, **stats):
    dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Staffed",
            vault_id=vault.id,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=1,
            max_health=100,
            health=100,
            **stats,
        ),
    )
    dweller.room_id = room_id
    async_session.add(dweller)
    await async_session.commit()
    return dweller


async def test_assign_correct_credits_existing_correct_staffing(async_session, vault):
    room = await _room(async_session, vault, SPECIALEnum.STRENGTH)
    await _dweller(async_session, vault, room.id, strength=8, agility=2)
    await _dweller(async_session, vault, room.id, strength=2, agility=8)

    objective = Objective(
        challenge="Assign a dweller correctly",
        reward="50 caps",
        category="starter",
        objective_type="assign_correct",
        target_entity={},
        target_amount=1,
    )
    assert await current_state_progress(async_session, vault.id, objective) == 1


async def test_assign_correct_ignores_unstaffed_rooms(async_session, vault):
    await _room(async_session, vault, SPECIALEnum.STRENGTH)
    objective = Objective(
        challenge="Assign a dweller correctly",
        reward="50 caps",
        category="starter",
        objective_type="assign_correct",
        target_entity={},
        target_amount=1,
    )
    assert await current_state_progress(async_session, vault.id, objective) == 0


async def test_build_additional_housing_credits_construction_not_upgrades(async_session, vault):
    seeded = await _room(async_session, vault, SPECIALEnum.CHARISMA, name="Living room", capacity=8, size=3)
    objective = Objective(
        challenge="Build a Living Quarters",
        reward="dweller:Wanderer",
        category="starter",
        objective_type="build",
        target_entity={"room_type": "living_room", "additional": True, "baseline_size": 3},
        target_amount=1,
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
    dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Explorer",
            vault_id=vault.id,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=1,
            max_health=100,
            health=100,
        ),
    )
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    explore = Objective(
        challenge="Send a dweller exploring",
        reward="50 caps",
        category="starter",
        objective_type="explore",
        target_entity={},
        target_amount=1,
    )
    expedition = Objective(
        challenge="Complete 3 Quests",
        reward="300 caps",
        category="weekly",
        objective_type="expedition",
        target_entity={},
        target_amount=3,
    )
    assert await current_state_progress(async_session, vault.id, explore) == 1
    assert await current_state_progress(async_session, vault.id, expedition) == 0
