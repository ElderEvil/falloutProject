"""Fresh-vault teaching rewards must fund the unchanged Office gate."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from app import crud
from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.models.objective import Objective
from app.models.outfit import Outfit
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.schemas.room import RoomBuild
from app.schemas.vault import VaultNumber
from app.services import catalog_service as data_loader
from app.services.dweller_service import dweller_service
from app.services.exploration_service import exploration_service
from app.services.family.breeding_service import breeding_service
from app.services.game_tick.family_tick import process_pregnancies_and_births
from app.services.item_service import item_service
from app.services.leveling_service import leveling_service
from app.services.progression.objectives.evaluators import evaluator_manager
from app.services.progression.objectives.evaluators.base import current_session_maker
from app.services.progression.objectives.guidance import current_state_progress, read_objectives
from app.services.quest_service import quest_service
from app.services.resource_manager_service import ResourceManager
from app.services.rewards.settlement import claim_objective_reward
from app.services.room_service import room_service
from app.services.vault_service import vault_service
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import ResourceConflictException
from app.utils.item_factory import build_catalog_item
from app.utils.seed_objectives import seed_objectives_from_json
from app.utils.seed_quests import seed_quests_from_json


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


@pytest.mark.parametrize(
    ("cohort", "scenario_number", "scenario"),
    [
        ("legacy", None, None),
        ("continuity", None, None),
        ("continuity", 67, "vault_67_short_rations"),
        ("continuity", 68, "vault_68_test"),
        ("continuity", 69, "vault_69_test"),
    ],
    ids=["legacy", "standard", "short-rations", "ratio", "inverse-ratio"],
)
async def test_starter_cohorts_reach_office_without_random_loot(
    async_session, superuser, objective_events, monkeypatch, tmp_path, cohort, scenario_number, scenario
):
    if cohort == "legacy":
        (tmp_path / "starter.json").write_text(
            (Path(__file__).parents[1] / "data/starter_pre_continuity.json").read_text()
        )
        await seed_objectives_from_json(async_session, tmp_path)
    else:
        await seed_objectives_from_json(async_session)
    # A random twin birth would push the deterministic 18-dweller arc to 19.
    monkeypatch.setattr(game_config.breeding, "twin_chance", 0.0)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", 0.0)
    start = VaultNumber(number=scenario_number or random_vault_number(), scenario=scenario)
    vault = await vault_service.initiate_vault(async_session, start, superuser.id)
    founders = {dweller.id for dweller in await crud.dweller.get_living_in_vault(async_session, vault.id)}
    initial_population = len(founders)
    storage = await crud.storage.storage.get_by_vault(async_session, vault.id)
    initial_rooms = await crud.room.get_all_by_vault(async_session, vault.id)
    assert initial_population == 9
    assert not any("radio" in room.name.lower() for room in initial_rooms)
    if cohort == "continuity":
        housing = next(o for o in await read_objectives(async_session, vault.id) if o.objective_type == "build")
        assert housing.progress == 0, "A fresh vault must earn additional housing through construction"
    if scenario_number in (68, 69):
        expected_variants = (
            {"Cal Vane", "Milo Rusk", "Galen Shaw", "Nolan Beck"}
            if scenario_number == 68
            else {"Iris Dane", "Ada Flint", "Mae Calder"}
        )
        advertised_recruits = {
            step.reward.removeprefix("dweller:")
            for step in await read_objectives(async_session, vault.id)
            if step.category == "starter" and step.reward.startswith("dweller:")
        }
        assert len(advertised_recruits) == 9
        assert expected_variants <= advertised_recruits
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
                missing = step.total - await crud.dweller.count_living_in_vault(async_session, vault.id)
                if cohort == "continuity":
                    assert missing <= 0, "Earned recruits must reach the Office without a pregnancy wait"
                if missing > 0:
                    residents = {f"{d.first_name} {d.last_name}": d for d in dwellers}
                    couples = [
                        (residents["Mara Voss"], residents["Elias Reed"]),
                        (residents["Tessa Ward"], residents["Owen Hale"]),
                    ]
                    assert missing == len(couples)
                    clock = Mock(wraps=datetime)
                    clock.now.return_value = datetime.now(UTC)
                    monkeypatch.setattr(import_module("app.utils.time"), "datetime", clock)
                    pregnancies = [
                        await breeding_service.create_pregnancy(async_session, mother.id, father.id)
                        for mother, father in couples
                    ]
                    duration = timedelta(hours=game_config.breeding.pregnancy_duration_hours)
                    assert all(p.due_at - p.conceived_at == duration for p in pregnancies)
                    clock.now.return_value += duration - timedelta(seconds=1)
                    assert (await process_pregnancies_and_births(async_session, vault.id))["births"] == 0
                    clock.now.return_value += timedelta(seconds=1)
                    assert (await process_pregnancies_and_births(async_session, vault.id))["births"] == missing
                    unavailable = await crud.pregnancy.get_unavailable_mother_ids(
                        async_session, vault.id, game_config.breeding.birth_cooldown_hours
                    )
                    assert {mother.id for mother, _ in couples} <= unavailable
            elif step.progress < step.total:
                worker = next(d for d in dwellers if d.is_mature and d.room_id is not None)
                await dweller_service.add_experience(
                    async_session,
                    worker,
                    leveling_service.calculate_xp_required(worker.level + 1) - worker.experience,
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
    assert granted_residents == (7 if cohort == "legacy" else 9)
    assert production_seconds <= 30 * 60
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 18
    assert vault.bottle_caps >= 200
    if cohort == "continuity":
        next_step = min(
            (
                o
                for o in await read_objectives(async_session, vault.id)
                if o.category == "starter" and not o.is_completed
            ),
            key=lambda o: o.sequence,
        )
        assert next_step.objective_type == "expedition"
        assert next_step.total == 1
        # The budget also affords a care building without selling starter equipment.
        assert vault.bottle_caps == 600
        await room_service.build_room(
            async_session, RoomBuild(vault_id=vault.id, room_name="Medbay", coordinate_x=16, coordinate_y=2)
        )
        await async_session.refresh(vault)
        assert vault.bottle_caps == 200
        weapons = await crud.weapon.get_multi(async_session, limit=100)
        assert any(w.name == "Hardened shotgun" and w.storage_id == storage.id for w in weapons)
        await seed_quests_from_json(async_session)
        missions = await quest_service.get_quests_for_vault(async_session, vault.id, available_only=True)
        first_mission = next(q for q in missions if q.title == "Getting Started")
        residents = await crud.dweller.get_living_in_vault(async_session, vault.id)
        if scenario_number in (68, 69):
            recruits = [dweller for dweller in residents if dweller.id not in founders]
            assert {dweller.display_name for dweller in recruits} == advertised_recruits
            assert sum(dweller.gender == GenderEnum.MALE for dweller in recruits) == (8 if scenario_number == 68 else 1)
        party = [d for d in residents if d.is_mature and d.room_id is None and d.status == DwellerStatusEnum.IDLE][:3]
        assert len(party) == 3
        for model, item_crud in ((Weapon, crud.weapon), (Outfit, crud.outfit)):
            equipment = [i for i in await item_crud.get_multi(async_session, limit=100) if i.storage_id == storage.id]
            assert len(equipment) >= len(party)
            for member, item in zip(party, equipment, strict=False):
                await item_service.equip_item(async_session, item_id=item.id, dweller_id=member.id, model=model)
        party_ids = [member.id for member in party]
        await quest_service.start_quest_for_vault(async_session, vault.id, first_mission.id, dweller_ids=party_ids)
        link = await crud.quest_crud.get_link(async_session, quest_id=first_mission.id, vault_id=vault.id)
        assert link.started_at is not None
        assert not link.is_completed
        assert not link.is_reward_ready
        roster = await crud.team_crud.get_quest_team(async_session, first_mission.id, vault.id)
        assert {member.dweller_id for member in roster} == set(party_ids)
        for member in party:
            await async_session.refresh(member)
            assert member.status == DwellerStatusEnum.QUESTING
            assert member.room_id is None
    else:
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
