"""B7 eager-load fan-out: pet bonuses apply through real CRUD paths.

``pet_modifiers_for`` reads ``entity.__dict__.get("pet")`` (via ``equipped_pet``), so a query that forgets
``selectinload(Dweller.pet)`` silently resolves the pet's effect to neutral. Each test exercises a real bonus-
consuming load site — the pet is created and equipped through ``crud.pet`` / ``crud.pet.equip``, never a hand-set
``__dict__`` — and asserts the delta vs. no pet.
"""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DamageChannel, RarityEnum
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.team import Team, TeamMember
from app.models.vault import Vault
from app.options.identity_modifiers import effective_stat
from app.schemas.room import RoomCreate
from app.services.combat.incident_sim_roster import snapshot_vault_defenders
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.tests.factory.rooms import create_fake_room
from app.utils.damage_reductions import damage_reductions

DOGMEAT = "Dogmeat (Fallout 4)"  # strength +2, max_health +20
PALLAS = "Pallas's Cat"  # incident_response_pct 0.25
BERNARD = "St. Bernard"  # radiation_resist_pct 0.25
WAREHOUSE = max(1, 100 + 20 - 40)


def _pet_data(name: str, **overrides) -> dict:
    return {"name": name, "rarity": RarityEnum.LEGENDARY, "value": 500, **overrides}


async def _equip_pet(async_session: AsyncSession, dweller: Dweller, name: str) -> None:
    pet = await crud.pet.create(async_session, _pet_data(name))
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)


async def _room(async_session: AsyncSession, vault: Vault):
    room_data = create_fake_room()
    room_data["name"] = "Power Generator"
    return await crud.room.create(db_session=async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))


async def _assign_to_room(async_session: AsyncSession, dweller: Dweller, room) -> None:
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()


async def _settled_exploration(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> Exploration:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.total_caps_found = 0
    exploration.total_distance = 100
    exploration.enemies_encountered = 0
    exploration.events = [{"type": "random", "description": "Found a cache"}]
    async_session.add(exploration)
    await async_session.commit()
    return exploration


async def _team(async_session: AsyncSession, dweller: Dweller, *, quest_id=None, exploration_id=None) -> Team:
    team = Team(vault_id=dweller.vault_id, quest_id=quest_id, exploration_id=exploration_id)
    async_session.add(team)
    await async_session.flush()
    async_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"))
    await async_session.commit()
    return team


@pytest.fixture
async def wounded(async_session: AsyncSession, dweller: Dweller) -> Dweller:
    dweller.max_health, dweller.radiation, dweller.strength = 100, 40, 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, DOGMEAT)
    return dweller


@pytest.fixture
async def strong(async_session: AsyncSession, dweller: Dweller) -> Dweller:
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, DOGMEAT)
    return dweller


@pytest.fixture
async def stationed(async_session: AsyncSession, dweller: Dweller, vault: Vault) -> Dweller:
    await _assign_to_room(async_session, dweller, await _room(async_session, vault))
    return dweller


@pytest.fixture
async def fighter(async_session: AsyncSession, dweller: Dweller, vault: Vault) -> Dweller:
    await _assign_to_room(async_session, dweller, await _room(async_session, vault))
    dweller.strength = dweller.agility = dweller.endurance = 5
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, DOGMEAT)
    return dweller


async def test_list_load_applies_pet_special_and_max_health(async_session: AsyncSession, vault: Vault, wounded) -> None:
    loaded = (await crud.dweller.get_multi_by_vault(async_session, vault.id))[0]
    assert effective_stat(loaded, "strength") == 7
    assert loaded.effective_max_health == WAREHOUSE


async def test_global_list_load_applies_pet_max_health(async_session: AsyncSession, wounded) -> None:
    loaded = (await crud.dweller.get_multi(async_session))[0]
    assert loaded.effective_max_health == WAREHOUSE


async def test_get_with_equipment_applies_pet_special(async_session: AsyncSession, strong) -> None:
    loaded = await crud.dweller.get_with_equipment(async_session, strong.id)
    assert loaded is not None
    assert effective_stat(loaded, "strength") == 7


async def test_arena_fighters_apply_pet_combat_power(async_session: AsyncSession, fighter: Dweller) -> None:
    fighters = await crud.dweller.get_arena_fighters(async_session, fighter.room_id)
    assert len(fighters) == 1
    assert effective_stat(fighters[0], "strength") == 7


async def test_arena_roster_applies_pet_max_health(async_session: AsyncSession, dweller: Dweller, fighter) -> None:
    dweller.max_health, dweller.radiation = 100, 40
    async_session.add(dweller)
    await async_session.commit()
    roster = await crud.dweller.get_arena_roster(async_session, fighter.room_id)
    assert len(roster) == 1
    assert roster[0].effective_max_health == WAREHOUSE


async def test_incident_defenders_apply_pet_resists(
    async_session: AsyncSession, dweller: Dweller, stationed: Dweller
) -> None:
    await _equip_pet(async_session, dweller, PALLAS)
    defenders = await crud.dweller.get_healthy_adults_in_room(async_session, stationed.room_id)
    assert len(defenders) == 1
    assert damage_reductions(defenders[0], DamageChannel.PHYSICAL).shares == (0.25,)
    assert damage_reductions(defenders[0], DamageChannel.FIRE).shares == (0.25,)


async def test_incident_defenders_apply_pet_radiation_resist(
    async_session: AsyncSession, dweller: Dweller, stationed: Dweller
) -> None:
    await _equip_pet(async_session, dweller, BERNARD)
    defenders = await crud.dweller.get_healthy_adults_in_room(async_session, stationed.room_id)
    radiation = damage_reductions(defenders[0], DamageChannel.RADIATION)
    assert radiation.shares == (0.25,)


async def test_incident_snapshot_defenders_apply_pet_resists(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    control = await snapshot_vault_defenders(async_session, vault.id)
    assert len(control) == 1
    assert control[0].reductions_physical.shares == ()
    assert control[0].reductions_fire.shares == ()
    await _equip_pet(async_session, dweller, PALLAS)
    defenders = await snapshot_vault_defenders(async_session, vault.id)
    assert len(defenders) == 1
    assert defenders[0].reductions_physical.shares == (0.25,)
    assert defenders[0].reductions_fire.shares == (0.25,)


async def test_tick_sweep_applies_pet_max_health(async_session: AsyncSession, vault: Vault, wounded) -> None:
    loaded = (await crud.dweller.get_all_in_vault(async_session, vault.id))[0]
    assert loaded.effective_max_health == WAREHOUSE


async def test_quest_eligible_applies_pet_stat(async_session: AsyncSession, vault: Vault, strong) -> None:
    eligible = await crud.quest_crud.get_quest_eligible_dwellers(async_session, vault.id)
    assert len(eligible) == 1
    assert effective_stat(eligible[0], "strength") == 7


async def test_quest_team_dwellers_apply_pet_combat_power(
    async_session: AsyncSession, vault: Vault, fighter: Dweller
) -> None:
    team = await _team(async_session, fighter, quest_id=uuid4())
    party = await crud.team_crud.get_quest_team_dwellers(async_session, team.quest_id, vault.id)
    assert len(party) == 1
    assert effective_stat(party[0], "strength") == 7


async def test_exploration_team_dwellers_apply_pet_combat_power(
    async_session: AsyncSession, vault: Vault, fighter: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, fighter.id, duration=4)
    await _team(async_session, fighter, exploration_id=exploration.id)
    party = await crud.team_crud.get_exploration_team_dwellers(async_session, exploration.id)
    assert len(party) == 1
    assert effective_stat(party[0], "strength") == 7


async def test_deleted_list_applies_pet_max_health(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, wounded
) -> None:
    dweller.is_deleted = True
    async_session.add(dweller)
    await async_session.commit()
    loaded = (await crud.dweller.get_deleted_by_vault(async_session, vault.id))[0]
    assert loaded.effective_max_health == WAREHOUSE


async def test_tradable_list_applies_pet_max_health(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, wounded
) -> None:
    dweller.is_deleted = True
    async_session.add(dweller)
    await async_session.commit()
    loaded = (await crud.dweller.get_tradable(async_session, vault_id=vault.id))[0]
    assert loaded.effective_max_health == WAREHOUSE


async def test_count_living_with_effective_stat_includes_pet(async_session: AsyncSession, vault: Vault, strong) -> None:
    assert await crud.dweller.count_living_with_effective_stat(async_session, vault.id, "strength", 7) == 1


async def test_resource_tick_applies_pet_stat(async_session: AsyncSession, vault: Vault, strong) -> None:
    await _assign_to_room(async_session, strong, await _room(async_session, vault))
    data = await crud.resource.resource.get_vault_resource_data(async_session, vault.id)
    loaded = [d for _, dwellers in data.rooms_with_dwellers for d in dwellers]
    assert len(loaded) == 1
    assert effective_stat(loaded[0], "strength") == 7


async def test_apply_rewards_applies_pet_xp_bonus(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    await _equip_pet(async_session, dweller, "CX404")  # xp_pct 0.25
    exploration = await _settled_exploration(async_session, vault, dweller)
    initial_xp = dweller.experience
    await rewards_service.apply_rewards(async_session, exploration)
    await async_session.refresh(dweller)
    assert dweller.experience > initial_xp
