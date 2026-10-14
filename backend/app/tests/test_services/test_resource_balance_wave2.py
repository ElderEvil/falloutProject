"""Resource catch-up must preserve recovery, reserves and fractional stock."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.models import Dweller, Room, Vault
from app.models.game_state import GameState
from app.services.resource_manager import ResourceManager


@pytest.mark.parametrize(("initial", "expected"), [(50, 25), (10, 10), (0, 0)])
async def test_offline_reserve_never_grants_stock(initial, expected):
    vault = Vault(power=initial, food=initial, water=initial, power_max=100, food_max=100, water_max=100)
    state = GameState(vault_id=uuid4(), last_activity_time=datetime.utcnow() - timedelta(hours=2))
    room = Room(size=30, tier=1)
    update, _ = ResourceManager().calculate_resource_window(vault, [room], 100, [], 3600, state=state)
    assert (update.power, update.food, update.water) == (expected, expected, expected)


async def test_active_vault_can_run_out():
    vault = Vault(power=50, food=50, water=50, power_max=100, food_max=100, water_max=100)
    state = GameState(vault_id=uuid4())
    update, _ = ResourceManager().calculate_resource_window(vault, [Room(size=100, tier=1)], 100, [], 60, state=state)
    assert update.power < 25
    assert update.food == 20


async def test_catchup_restores_nonpower_production_after_generator_recovers():
    vault = Vault(power=0, food=0, water=0, power_max=100, food_max=100, water_max=100)
    rooms = [
        Room(name=name, category=RoomTypeEnum.PRODUCTION, ability=stat, output=28, size=3, tier=1)
        for name, stat in [
            ("Power Generator", SPECIALEnum.STRENGTH),
            ("Diner", SPECIALEnum.AGILITY),
            ("Water Treatment", SPECIALEnum.PERCEPTION),
        ]
    ]
    crews = [(room, [Dweller(strength=5, agility=5, perception=5)]) for room in rooms]
    manager = ResourceManager()
    one_update, _ = manager.calculate_resource_window(vault, rooms, 3, crews, 3600)
    state = GameState(vault_id=uuid4())
    for _ in range(60):
        update, _ = manager.calculate_resource_window(vault, rooms, 3, crews, 60, state=state)
        for key in ("power", "food", "water"):
            setattr(vault, key, getattr(update, key))
    assert (one_update.power, one_update.food, one_update.water) == (vault.power, vault.food, vault.water)
    assert one_update.food == 100


async def test_fractional_changes_survive_repeated_ticks():
    vault = Vault(power=50, food=50, water=50, power_max=100, food_max=100, water_max=100)
    state = GameState(vault_id=uuid4())
    manager = ResourceManager()
    for _ in range(10):
        update, _ = manager.calculate_resource_window(vault, [], 1, [], 60, state=state)
        vault.food, vault.water = update.food, update.water
    assert vault.food == 47
    assert vault.water == 47


async def test_fractional_carry_survives_database_reload(async_session, vault):
    from app.models.game_state import GameState

    vault.food_max = vault.water_max = 1000
    async_session.add(vault)
    state = GameState(vault_id=vault.id, resource_remainders={"food": 0.2, "water": 0.2})
    async_session.add(state)
    await async_session.commit()
    state_id, vault_id = state.id, vault.id
    async_session.expire_all()
    loaded = await async_session.get(GameState, state_id)
    vault = await async_session.get(Vault, vault_id)
    update, _ = ResourceManager().calculate_resource_window(vault, [], 1, [], 60, state=loaded)
    assert loaded.resource_remainders["food"] == pytest.approx(-0.1)


async def test_population_counts_only_present_living_dwellers(async_session, vault):
    from app.core.enums import AgeGroupEnum, DwellerStatusEnum
    from app.crud.resource import resource

    for fields in [
        {},
        {"age_group": AgeGroupEnum.CHILD},
        {"age_group": AgeGroupEnum.TEEN},
        {"is_dead": True},
        {"is_deleted": True},
        {"status": DwellerStatusEnum.EXPLORING},
        {"status": DwellerStatusEnum.QUESTING},
        {"status": DwellerStatusEnum.DEAD},
    ]:
        async_session.add(
            Dweller(
                vault_id=vault.id, first_name="Balance", last_name="Worker", gender="male", rarity="common", **fields
            )
        )
    await async_session.commit()
    data = await resource.get_vault_resource_data(async_session, vault.id)
    assert data.dweller_count == pytest.approx(2.4)
