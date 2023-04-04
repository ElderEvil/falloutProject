from abc import ABC
from enum import Enum

from Game.Items.Items import Item, Stimpak, RadAway
from Game.Vault.Dwellers import Dweller
from Game.Vault.Resources import ResourceType


class RoomType(Enum):
    CAPACITY = "Capacity"
    CRAFTING = "Crafting"
    MISC = "Misc"
    PRODUCTION = "Production"
    QUESTS = "Quests"
    THEME = "Theme"
    TRAINING = "Training"


class AbstractRoom(ABC):
    name: str
    type: RoomType
    population_required: int
    base_cost: int
    incremental_cost: int
    workers: list

    def __init__(self, *args, **kwargs):
        self.workers = []

    def add_worker(self, dweller: Dweller):
        if len(self.workers) < 2:
            self.workers.append(dweller)
            dweller.current_room = self
            print(f"{dweller.full_name} is now working in {self.name}")
        else:
            print(f"{self.name} is already at worker capacity")

    def remove_worker(self, dweller: Dweller):
        if dweller in self.workers:
            self.workers.remove(dweller)
            dweller.current_room = None
            print(f"{dweller.full_name} is no longer working in {self.name}")
        else:
            print(f"{dweller.full_name} is not working in {self.name}")

    def __str__(self):
        return str(self.name)


class TieredRoom(AbstractRoom):
    tier: int
    max_tier: int
    t2_upgrade_cost: int
    t3_upgrade_cost: int

    def __init__(self, tier: int = 1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tier = tier

    def upgrade_tier_cost(self):
        match self.tier:
            case 1:
                return self.t2_upgrade_cost
            case 2:
                return self.t3_upgrade_cost
            case _:
                print("Invalid tier number")

    def upgrade_tier(self):
        if self.tier < self.max_tier:
            self.tier += 1
        else:
            print(f"{self.name} already has highest tier")


class ProductionRoom(TieredRoom):
    type = RoomType.PRODUCTION
    ability: str
    resource_type: ResourceType | Item
    amount_multiplier: int
    capacity_multiplier: int

    @property
    def amount(self):
        return self.tier * self.amount_multiplier

    @property
    def capacity(self):
        return self.capacity_multiplier * self.tier + 1

    def _get_stat_sum(self):
        return sum(map(lambda w: w.getattr(self.ability), self.workers))

    def produce_resources(self, amount: int):
        for worker in self.workers:
            worker.add_happiness()
            worker.add_experience(amount)
        self.resource_type.produce(self.amount)


class CapacityRoom(TieredRoom):
    type = RoomType.CAPACITY


class MiscRoom(AbstractRoom):
    type = RoomType.MISC
    base_cost = 0
    incremental_cost = 0


class QuestRoom(AbstractRoom):
    type = RoomType.QUESTS


class CraftingRoom(TieredRoom):
    type = RoomType.CRAFTING


class TrainingRoom(TieredRoom):
    type = RoomType.TRAINING
    ability: str

    def train_workers(self):
        for dweller in self.workers:
            dweller.add_special(self.ability)
            dweller.add_happiness()


class VaultDoor(MiscRoom):
    name = "Vault door"
    population_required = 0
    t2_upgrade_cost = 500
    t3_upgrade_cost = 2000
    size = 6


class Elevator(MiscRoom):
    name = "Elevator"
    population_required = 0
    max_tier = 1
    size = 1


class LivingRoom(CapacityRoom):
    name = "Living Room"
    ability = "charisma"
    population_required = 0
    t2_upgrade_cost = 500
    t3_upgrade_cost = 1500
    size = 3


class PowerGenerator(ProductionRoom):
    name = "Power generator"
    ability = 'strength'
    t2_upgrade_cost = 500
    t3_upgrade_cost = 1_500
    population_required = 0
    amount_multiplier = 100
    capacity_multiplier = 25
    resource_type: ResourceType = ResourceType("Power", 100)


class DiningRoom(ProductionRoom):
    name = "Dining room"
    ability = "agility"
    t2_upgrade_cost = 500
    t3_upgrade_cost = 1_500
    population_required = 0
    amount_multiplier = 100
    capacity_multiplier = 25
    resource_type: ResourceType = ResourceType("Food", 100)


class WaterTreatment(ProductionRoom):
    name = "Water Treatment"
    ability = "perception"
    population_required = 0
    t2_upgrade_cost = 500
    t3_upgrade_cost = 1_500
    amount_multiplier = 100
    capacity_multiplier = 25
    resource_type: ResourceType = ResourceType("Food", 100)


class StorageRoom(CapacityRoom):
    name = "Storage room"
    ability = "endurance"
    population_required = 12
    base_cost = 300
    incremental_cost = 75
    t2_upgrade_cost = 750
    t3_upgrade_cost = 1_500


class Medbay(ProductionRoom):
    name = "Medbay"
    ability = "intelligence"
    population_required = 14
    t2_upgrade_cost = 1_000
    t3_upgrade_cost = 3_000
    capacity_multiplier = 10
    resource_type = Stimpak

    @property
    def capacity(self):
        return self.capacity_multiplier * self.tier


class ScienceLab(ProductionRoom):
    name = "Science lab"
    ability = "intelligence"
    population_required = 16
    t2_upgrade_cost = 1_000
    t3_upgrade_cost = 3_000
    capacity_multiplier = 10
    resource_type = RadAway

    @property
    def capacity(self):
        return self.capacity_multiplier * self.tier


class OverseerOffice(QuestRoom):
    name = "Overseer's office"
    population_required = 18
    t2_upgrade_cost = 3_500
    t3_upgrade_cost = 15_000


class RadioStudio(ProductionRoom):
    name = "Radio studio"
    ability = "charisma"
    population_required = 20
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class WeaponWorkshop(CraftingRoom):
    name = "Weapon workshop"
    population_required = 22
    base_cost = 800
    incremental_cost = 600
    t2_upgrade_cost = 8_000
    t3_upgrade_cost = 60_000


class WeightRoom(TrainingRoom):
    name = "Weight room"
    ability = "strength"
    population_required = 24
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class AthleticsRoom(TrainingRoom):
    name = "Athletics room"
    ability = "agility"
    population_required = 26
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class Armory(TrainingRoom):
    name = "Armory"
    ability = "perception"
    population_required = 28
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class Classroom(TrainingRoom):
    name = "Classroom"
    ability = "intelligence"
    population_required = 30
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class OutfitWorkshop(CraftingRoom):
    name = "Outfit workshop"
    population_required = 32
    base_cost = 1_200
    incremental_cost = 900
    t2_upgrade_cost = 12_000
    t3_upgrade_cost = 90_000


class FitnessRoom(TrainingRoom):
    name = "Fitness room"
    ability = "endurance"
    population_required = 35
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class Lounge(TrainingRoom):
    name = "Lounge"
    ability = "charisma"
    population_required = 40
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class ThemeWorkshop(TieredRoom):
    type = RoomType.THEME
    name = "Theme workshop"
    population_required = 42
    base_cost = 3_200
    incremental_cost = 2_400
    t2_upgrade_cost = 16_000
    t3_upgrade_cost = 12_000


class GameRoom(TrainingRoom):
    name = "Game room"
    ability = "luck"
    population_required = 45
    base_cost = 600
    incremental_cost = 150
    t2_upgrade_cost = 1_500
    t3_upgrade_cost = 4_500


class Barbershop(MiscRoom):
    name = "Barbershop"
    population_required = 42
    base_cost = 10_000
    incremental_cost = 5_000
    t2_upgrade_cost = 50_000


class NuclearReactor(ProductionRoom):
    name = "Nuclear reactor"
    ability = "strength"
    population_required = 60
    base_cost = 1_200
    incremental_cost = 300
    t2_upgrade_cost = 3_000
    t3_upgrade_cost = 9_000
    capacity_multiplier = 100


class Garden(ProductionRoom):
    name = "Garden"
    ability = "agility"
    population_required = 70
    base_cost = 1_200
    incremental_cost = 300
    t2_upgrade_cost = 3_000
    t3_upgrade_cost = 9_000
    capacity_multiplier = 25


class WaterPurification(ProductionRoom):
    name = "Water purification"
    ability = "perception"
    population_required = 80
    base_cost = 1_200
    incremental_cost = 300
    t2_upgrade_cost = 3_000
    t3_upgrade_cost = 9_000
    capacity_multiplier = 25


class NukaColaBottler(ProductionRoom):
    name = "Nuka-Cola bottler"
    ability = "endurance"
    population_required = 100
    base_cost = 3_000
    incremental_cost = 750
    t2_upgrade_cost = 15_000
    t3_upgrade_cost = 45_000
    capacity_multiplier = 50
