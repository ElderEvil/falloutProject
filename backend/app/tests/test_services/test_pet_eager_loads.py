"""B7 eager-load fan-out: pet bonuses apply through real CRUD paths.

``pet_modifiers_for`` reads ``entity.__dict__.get("pet")`` (via
``equipped_pet``), so a query that forgets ``selectinload(Dweller.pet)``
silently resolves the pet's effect to neutral. These tests prove each
bonus-consuming load site eager-loads the pet by exercising the real CRUD
accessor — the pet is created and equipped through ``crud.pet`` /
``crud.pet.equip``, never a hand-set ``__dict__`` — and asserting the delta
vs. no pet.
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
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.tests.factory.rooms import create_fake_room
from app.utils.damage_reductions import damage_reductions


def _pet_data(name: str, **overrides) -> dict:
    return {"name": name, "rarity": RarityEnum.LEGENDARY, "value": 500, **overrides}


async def _equip_pet(async_session: AsyncSession, dweller: Dweller, name: str) -> None:
    pet = await crud.pet.create(async_session, _pet_data(name))
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)


async def _room(async_session: AsyncSession, vault: Vault):
    room_data = create_fake_room()
    room_data["name"] = "Power Generator"
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


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


@pytest.mark.asyncio
async def test_list_load_applies_pet_special_and_max_health(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_multi_by_vault (roster list) applies the pet's SPECIAL and max_health."""
    dweller.strength = 5
    dweller.max_health = 100
    dweller.radiation = 40
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")  # strength +2, max_health +20

    loaded = (await crud.dweller.get_multi_by_vault(async_session, vault.id))[0]
    assert effective_stat(loaded, "strength") == 7
    assert loaded.effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_global_list_load_applies_pet_max_health(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_multi (superuser global list) applies the pet's max_health."""
    dweller.max_health = 100
    dweller.radiation = 40
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    loaded = (await crud.dweller.get_multi(async_session))[0]
    assert loaded.effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_get_with_equipment_applies_pet_special(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_with_equipment (exploration combat profile) applies the pet's SPECIAL."""
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    loaded = await crud.dweller.get_with_equipment(async_session, dweller.id)
    assert loaded is not None
    assert effective_stat(loaded, "strength") == 7


@pytest.mark.asyncio
async def test_arena_fighters_apply_pet_combat_power(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_arena_fighters applies the pet's SPECIAL through combat_power."""
    room = await _room(async_session, vault)
    await _assign_to_room(async_session, dweller, room)
    dweller.strength = 5
    dweller.agility = 5
    dweller.endurance = 5
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")  # strength +2

    fighters = await crud.dweller.get_arena_fighters(async_session, room.id)
    assert len(fighters) == 1
    assert effective_stat(fighters[0], "strength") == 7


@pytest.mark.asyncio
async def test_arena_roster_applies_pet_max_health(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_arena_roster applies the pet's max_health to the roster wire value."""
    room = await _room(async_session, vault)
    await _assign_to_room(async_session, dweller, room)
    dweller.max_health = 100
    dweller.radiation = 40
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    roster = await crud.dweller.get_arena_roster(async_session, room.id)
    assert len(roster) == 1
    assert roster[0].effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_incident_defenders_apply_pet_resists(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_healthy_adults_in_room applies the pet's incident/radiation resists."""
    room = await _room(async_session, vault)
    await _assign_to_room(async_session, dweller, room)
    await _equip_pet(async_session, dweller, "Pallas's Cat")  # incident_response_pct 0.25

    defenders = await crud.dweller.get_healthy_adults_in_room(async_session, room.id)
    assert len(defenders) == 1
    physical = damage_reductions(defenders[0], DamageChannel.PHYSICAL)
    assert physical.shares == (0.25,)
    fire = damage_reductions(defenders[0], DamageChannel.FIRE)
    assert fire.shares == (0.25,)


@pytest.mark.asyncio
async def test_incident_defenders_apply_pet_radiation_resist(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_healthy_adults_in_room applies the pet's radiation resist."""
    room = await _room(async_session, vault)
    await _assign_to_room(async_session, dweller, room)
    await _equip_pet(async_session, dweller, "St. Bernard")  # radiation_resist_pct 0.25

    defenders = await crud.dweller.get_healthy_adults_in_room(async_session, room.id)
    radiation = damage_reductions(defenders[0], DamageChannel.RADIATION)
    assert radiation.shares == (0.25,)


@pytest.mark.asyncio
async def test_tick_sweep_applies_pet_max_health(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_all_in_vault (game-tick sweep) applies the pet's max_health."""
    dweller.max_health = 100
    dweller.radiation = 40
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    loaded = (await crud.dweller.get_all_in_vault(async_session, vault.id))[0]
    assert loaded.effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_quest_eligible_applies_pet_stat(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_quest_eligible_dwellers applies the pet's SPECIAL to STAT gates."""
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    eligible = await crud.quest_crud.get_quest_eligible_dwellers(async_session, vault.id)
    assert len(eligible) == 1
    assert effective_stat(eligible[0], "strength") == 7


@pytest.mark.asyncio
async def test_quest_team_dwellers_apply_pet_combat_power(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_quest_team_dwellers applies the pet's SPECIAL through combat_power."""
    dweller.strength = 5
    dweller.agility = 5
    dweller.endurance = 5
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    team = Team(vault_id=vault.id, quest_id=uuid4())
    async_session.add(team)
    await async_session.flush()
    async_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"))
    await async_session.commit()

    party = await crud.team_crud.get_quest_team_dwellers(async_session, team.quest_id, vault.id)
    assert len(party) == 1
    assert effective_stat(party[0], "strength") == 7


@pytest.mark.asyncio
async def test_exploration_team_dwellers_apply_pet_combat_power(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_exploration_team_dwellers applies the pet's SPECIAL through combat_power."""
    dweller.strength = 5
    dweller.agility = 5
    dweller.endurance = 5
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    team = Team(vault_id=vault.id, exploration_id=exploration.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"))
    await async_session.commit()

    party = await crud.team_crud.get_exploration_team_dwellers(async_session, exploration.id)
    assert len(party) == 1
    assert effective_stat(party[0], "strength") == 7


@pytest.mark.asyncio
async def test_deleted_list_applies_pet_max_health(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_deleted_by_vault (deleted roster) applies the pet's max_health."""
    dweller.max_health = 100
    dweller.radiation = 40
    dweller.is_deleted = True
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    loaded = (await crud.dweller.get_deleted_by_vault(async_session, vault.id))[0]
    assert loaded.effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_tradable_list_applies_pet_max_health(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_tradable (trading post) applies the pet's max_health."""
    dweller.max_health = 100
    dweller.radiation = 40
    dweller.is_deleted = True
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    loaded = (await crud.dweller.get_tradable(async_session, vault_id=vault.id))[0]
    assert loaded.effective_max_health == max(1, 100 + 20 - 40)


@pytest.mark.asyncio
async def test_count_living_with_effective_stat_includes_pet(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """count_living_with_effective_stat counts the pet-boosted stat."""
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")  # strength +2 -> 7

    assert await crud.dweller.count_living_with_effective_stat(async_session, vault.id, "strength", 7) == 1


@pytest.mark.asyncio
async def test_resource_tick_applies_pet_stat(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_vault_resource_data (production tick) applies the pet's SPECIAL."""
    room = await _room(async_session, vault)
    await _assign_to_room(async_session, dweller, room)
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await _equip_pet(async_session, dweller, "Dogmeat (Fallout 4)")

    data = await crud.resource.resource.get_vault_resource_data(async_session, vault.id)
    loaded = [d for _, dwellers in data.rooms_with_dwellers for d in dwellers]
    assert len(loaded) == 1
    assert effective_stat(loaded[0], "strength") == 7


@pytest.mark.asyncio
async def test_apply_rewards_applies_pet_xp_bonus(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """apply_rewards grants the pet's xp_pct through the real settlement path."""
    await _equip_pet(async_session, dweller, "CX404")  # xp_pct 0.25
    exploration = await _settled_exploration(async_session, vault, dweller)
    initial_xp = dweller.experience

    await rewards_service.apply_rewards(async_session, exploration)

    await async_session.refresh(dweller)
    assert dweller.experience > initial_xp
