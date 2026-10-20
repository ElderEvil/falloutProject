"""Fresh-vault teaching rewards must fund the unchanged Office gate."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.models.objective import Objective
from app.models.outfit import Outfit
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.options.races import can_breed
from app.schemas.room import RoomBuild
from app.schemas.vault import VaultNumber
from app.services import catalog_service as data_loader
from app.services.dweller_service import dweller_service
from app.services.exploration_service import exploration_service
from app.services.family.breeding_service import breeding_service
from app.services.game_tick.family_tick import process_pregnancies_and_births
from app.services.item_service import item_service
from app.services.progression.objectives.evaluators import evaluator_manager
from app.services.progression.objectives.evaluators.base import current_session_maker
from app.services.progression.objectives.guidance import current_state_progress, read_objectives
from app.services.resource_manager import ResourceManager
from app.services.rewards.settlement import claim_objective_reward
from app.services.room_service import room_service
from app.services.vault_service import vault_service
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import ResourceConflictException
from app.utils.item_factory import build_catalog_item
from app.utils.seed_objectives import seed_objectives_from_json


@pytest.fixture
def objective_events(async_session):
    """Bind real event handlers to this test's SQLite transaction."""

    @asynccontextmanager
    async def session_scope():
        yield async_session

    token = current_session_maker.set(session_scope)
    was_initialized = evaluator_manager.is_initialized
    evaluator_manager.initialize()
    yield
    if not was_initialized:
        evaluator_manager.shutdown()
    current_session_maker.reset(token)


async def test_fresh_starter_rewards_reach_office_without_loot(async_session, superuser, objective_events):
    await seed_objectives_from_json(async_session)
    vault = await vault_service.initiate_vault(async_session, VaultNumber(number=random_vault_number()), superuser.id)
    initial_population = await crud.dweller.count_living_in_vault(async_session, vault.id)
    storage = await crud.storage.storage.get_by_vault(async_session, vault.id)
    initial_rooms = await crud.room.get_all_by_vault(async_session, vault.id)
    assert initial_population == 9
    assert not any("radio" in room.name.lower() for room in initial_rooms)
    production_seconds = 0
    granted_residents = 0

    while True:
        objectives = await read_objectives(async_session, vault.id)
        step = min(
            (o for o in objectives if o.category == "starter" and not o.is_completed),
            key=lambda o: o.sequence,
        )
        target = step.target_entity or {}
        dwellers = await crud.dweller.get_living_in_vault(async_session, vault.id)
        rooms = await crud.room.get_all_by_vault(async_session, vault.id)

        if step.objective_type == "build":
            name, x, y = {
                "living_room": ("Living room", 10, 1),
                "power_generator": ("Power generator", 0, 1),
                "overseers_office": ("Overseer's Office", 10, 2),
            }[target["room_type"]]
            before_caps = vault.bottle_caps
            room = await room_service.build_room(
                async_session, RoomBuild(vault_id=vault.id, room_name=name, coordinate_x=x, coordinate_y=y)
            )
            await async_session.refresh(vault)
            if target["room_type"] == "overseers_office":
                assert room.population_required == 18
                assert before_caps - vault.bottle_caps == 1_000
        elif step.objective_type == "explore":
            explorer = next(d for d in dwellers if d.first_name == "Juno")
            await exploration_service.send_dweller(async_session, vault.id, explorer.id, duration=2)
        elif step.objective_type == "equip":
            receiver = next(d for d in dwellers if d.is_mature and d.room_id is None and d.status != "exploring")
            model = Weapon if target["item_type"] == "weapon" else Outfit
            item_crud = crud.weapon if model is Weapon else crud.outfit
            items = await item_crud.get_multi(async_session, limit=100)
            item = next(
                i for i in items if i.storage_id == storage.id and (model is Weapon or i.name == "Wasteland gear")
            )
            await item_service.equip_item(async_session, item_id=item.id, dweller_id=receiver.id, model=model)
        elif step.objective_type == "collect":
            # Actual production, including output beyond the storage limit. No loot or reward events.
            for _ in range(60):
                resources, events = await ResourceManager().process_vault_resources(async_session, vault.id, 60)
                await crud.vault.update(async_session, vault.id, resources)
                await ResourceManager.emit_production_events(vault.id, events)
                production_seconds += 60
                link = await crud.objective_crud.get_link_for_update(async_session, step.id, vault.id)
                if link.progress >= link.total:
                    break
            else:
                pytest.fail(f"Production lesson did not complete: {step.challenge}")
        elif step.objective_type == "assign" and step.progress < step.total:
            room = next(r for r in rooms if r.name.lower() == "power generator")
            worker = next(d for d in dwellers if d.is_mature and d.room_id is None and d.status != "exploring")
            await dweller_service.move_to_room(async_session, worker.id, room.id)
        elif step.objective_type == "reach":
            if target["reach_type"] == "dweller_count":
                for _ in range(10):
                    if await crud.dweller.count_living_in_vault(async_session, vault.id) >= step.total:
                        break
                    mother = next(
                        d
                        for d in dwellers
                        if d.age_group == AgeGroupEnum.ADULT and d.gender == GenderEnum.FEMALE and can_breed(d)
                    )
                    father = next(
                        d
                        for d in dwellers
                        if d.age_group == AgeGroupEnum.ADULT and d.gender == GenderEnum.MALE and can_breed(d)
                    )
                    pregnancy = await breeding_service.create_pregnancy(async_session, mother.id, father.id)
                    pregnancy.due_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
                    async_session.add(pregnancy)
                    await async_session.commit()
                    await process_pregnancies_and_births(async_session, vault.id)
                else:
                    pytest.fail(f"Breeding did not reach {step.challenge}")
            elif step.progress < step.total:
                worker = next(d for d in dwellers if d.is_mature and d.room_id is not None)
                await dweller_service.add_experience(
                    async_session, worker, crud.dweller.calculate_experience_required(worker)
                )

        before_population = await crud.dweller.count_living_in_vault(async_session, vault.id)
        link = await claim_objective_reward(async_session, step.id, vault.id)
        granted_residents += await crud.dweller.count_living_in_vault(async_session, vault.id) - before_population
        with pytest.raises(ResourceConflictException):
            await claim_objective_reward(async_session, step.id, vault.id)
        assert link.is_completed
        if target.get("room_type") == "overseers_office":
            break

    await async_session.refresh(vault)
    assert granted_residents == 7
    assert production_seconds <= 30 * 60
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 18
    assert vault.bottle_caps >= 200
    # The next scrap lesson has a guaranteed rare item; no random drop is required.
    weapons = await crud.weapon.get_multi(async_session, limit=100)
    rare_reward = next(w for w in weapons if w.name == "Hardened shotgun" and w.storage_id == storage.id)
    assert rare_reward.rarity == RarityEnum.RARE
    await item_service.scrap_item(async_session, item_id=rare_reward.id, model=Weapon)
    scrap = next(
        o
        for o in await read_objectives(async_session, vault.id)
        if o.category == "starter" and o.objective_type == "scrap"
    )
    assert scrap.progress == scrap.total


@pytest.mark.parametrize("model", [Weapon, Outfit])
async def test_equipment_lessons_credit_only_the_matching_committed_action(
    async_session, vault, dweller, objective_events, model
):
    objectives = [
        Objective(
            challenge=f"Equip a {kind}",
            reward="50 caps",
            category="starter",
            sequence=index,
            objective_type="equip",
            target_entity={"item_type": kind},
            target_amount=1,
        )
        for index, kind in enumerate(("weapon", "outfit"))
    ]
    links = [VaultObjectiveProgressLink(vault_id=vault.id, objective_id=o.id) for o in objectives]
    item = build_catalog_item(
        "weapon" if model is Weapon else "outfit",
        "Hunting rifle" if model is Weapon else "Wasteland gear",
        RarityEnum.COMMON,
        weapons_data=data_loader.load_weapons(),
        outfits_data=data_loader.load_outfits(),
    )
    async_session.add_all([*objectives, *links, item])
    await async_session.commit()
    await item_service.equip_item(async_session, item_id=item.id, dweller_id=dweller.id, model=model)
    for objective, link in zip(objectives, links, strict=True):
        await async_session.refresh(link)
        expected = int(objective.target_entity["item_type"] == model.__name__.lower())
        assert link.progress == expected
        assert await current_state_progress(async_session, vault.id, objective) == expected
        assert not link.is_completed  # Equipment earns the reward; claiming still remains explicit.

    # Equipped items belonging to deceased residents cannot satisfy a state-based lesson.
    dweller.is_dead = True
    async_session.add(dweller)
    await async_session.commit()
    assert all([await current_state_progress(async_session, vault.id, o) == 0 for o in objectives])
