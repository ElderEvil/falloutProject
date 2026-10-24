from app.models import Dweller, Storage
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.services.resource_manager import ResourceManager


def _room() -> Room:
    return Room(
        name="Diner",
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.AGILITY,
        output=10,
        tier=2,
        size=2,
        size_min=1,
        size_max=3,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
    )


def test_calculate_room_production_matches_batched_production() -> None:
    manager = ResourceManager()
    room = _room()
    worker = Dweller(agility=7, luck=3)

    batched = manager._calculate_production([(room, [worker])], 300, current_power=10)
    per_room = manager.calculate_room_production(room, [worker], 300)

    assert batched == per_room
    assert per_room["food"] > 0


def test_apply_room_payout_clamps_primary_and_medical_stocks() -> None:
    manager = ResourceManager()
    vault = Vault(power=90, power_max=100, food=0, food_max=100, water=0, water_max=100)
    storage = Storage(stimpack=4, radaway=0)

    applied = manager.apply_room_payout(
        vault,
        storage,
        {"stimpack": 5, "radaway": 0},
        {"power": 20.0, "food": 5.0, "water": 0.0, "stimpack": 3.0, "radaway": 0.0},
    )

    assert applied == {"power": 10, "food": 5, "water": 0, "stimpack": 1, "radaway": 0}
    assert vault.power == 100
    assert vault.food == 5
    assert storage.stimpack == 5
