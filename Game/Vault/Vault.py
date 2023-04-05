from statistics import mean
from typing import Type

from Game.Vault.Dwellers import Dweller
from Game.Vault.Resources import ResourceType
from Game.Vault.Rooms import AbstractRoom
from Game.Vault.Storage import Storage
from Game.Vault.utilities.RoomBuilder import RoomBuilder
from Game.settings import *
from Game.logger_settings import logger


class Vault:

    def __init__(self, name: str):
        self._rb = RoomBuilder()
        self.name = name
        self.bottle_caps = 1000
        self.storage = Storage()
        self.dwellers = []
        self.rooms = []

        self.power = ResourceType('Power', 100)
        self.food = ResourceType('Food', 100)
        self.water = ResourceType('Water', 100)

        self.__populate_vault()

    def __populate_vault(self):
        vault_door = self.construct_room("Vault door")
        for _ in range(DEFAULT_VAULT_DWELLERS_NUMBER):
            dweller = Dweller()
            vault_door.add_worker(dweller)
            self.add_dweller(dweller)

    @property
    def population(self):
        return len(self.dwellers)

    @property
    def happiness(self):
        return mean(map(lambda d: d.happiness, self.dwellers))

    def add_dweller(self, dweller: Dweller):
        """
        Adds the given Dweller instance to the vault.

        :param dweller: The Dweller instance to add to the vault.
        """
        self.dwellers.append(dweller)
        logger.info(f'Added {dweller} to {dweller.current_room}')

    def remove_dweller(self, dweller: Dweller):
        """
        Removes the given Dweller instance from the vault.

        :param dweller: The Dweller instance to remove from the vault.
        """
        self.dwellers.remove(dweller)
        logger.info(f'{dweller} left {self.name}')

    def get_power_consumption(self):
        """
        Returns the amount of power to be consumed based on the number of rooms in the vault.
        """

        return len(self.rooms) * POWER_CONSUMPTION_MULTIPLIER

    def get_food_consumption(self):
        """
        Returns the amount of food to be consumed based on the number of dwellers in the vault.
        """
        return self.population * FOOD_CONSUMPTION_MULTIPLIER

    def get_water_consumption(self):
        """
        Returns the amount of water to be consumed based on the number of dwellers in the vault.
        """
        return self.population * WATER_CONSUMPTION_MULTIPLIER

    def consume_resources(self, food_amount: int, water_amount: int, power_amount: int) -> None:
        if not self.food.consume(food_amount):
            raise ValueError('Not enough food!')
        if not self.water.consume(water_amount):
            raise ValueError('Not enough water!')
        if not self.power.consume(power_amount):
            raise ValueError('Not enough power!')

    def produce_resources(self, food_amount: int, water_amount: int, power_amount: int):
        self.food.produce(min(food_amount, self.food.max_amount - self.food.current_amount))
        self.water.produce(min(water_amount, self.water.max_amount - self.water.current_amount))
        self.power.produce(min(power_amount, self.power.max_amount - self.power.current_amount))

    def calculate_total_production_rates(self) -> list[int]:
        """
        Calculates the total production rates for each resource based on the number of production rooms and their tier.

        :return: A list containing the total production rates for food, water, and power.
        """
        ...

    def get_available_room_types(self) -> list:
        """
        Filters and returns a list of room types that can be built based on the current number of dwellers in the vault.

        :return: A list of room types that can be built.
        :raises logger.error: If no buildable rooms are found.
        """
        rooms = self._rb.filter_by_population_required(self.population).build()
        logger.debug(f"Available rooms:{[r.name for r in rooms]}")
        if not rooms:
            logger.info("No buildable rooms found")
        return rooms

    def calculate_room_cost(self, room_type: Type[AbstractRoom]) -> int:
        """
        Calculates the total cost of building a room of the given type.

        :param room_type: The type of room to calculate the cost for.
        :return: The total cost of building the room.
        """
        same_rooms_num = sum(1 for r in self.rooms if r.name == room_type.name)
        return room_type.base_cost + room_type.incremental_cost * same_rooms_num

    def calculate_remaining_bottle_caps(self, room_type: Type[AbstractRoom]) -> int:
        """
        Calculates the remaining number of bottle caps needed to build a room of the given type.

        :param room_type: The type of room to calculate the remaining cost for.
        :return: The remaining number of bottle caps needed to build the room.
        """
        total_cost = self.calculate_room_cost(room_type)
        return max(0, total_cost - self.bottle_caps)

    def construct_room(self, room_name: str) -> AbstractRoom:
        """
        Constructs a new room of the specified type and adds it to the vault.

        :param room_name: The name of the room to construct.
        :return: The constructed room.
        :raises ValueError: If no room types are found with the specified name or if there are insufficient bottle caps.
        """
        room_to_build = self._rb.get_by_name(room_name)
        if not room_to_build:
            raise ValueError(f"No room found with name {room_name}")

        remaining_caps = self.calculate_remaining_bottle_caps(room_to_build)
        if remaining_caps > 0:
            raise ValueError(f"Not enough bottle caps for {room_name}. You need {remaining_caps} more.")

        room = self._rb.build_room(room_to_build)
        self.rooms.append(room)
        return room

    def show_status(self, verbose: bool = False):
        """
        Displays the current status of the vault, including the number of dwellers, happiness, resources, rooms
        and bottle caps.

        :param verbose: If True, displays detailed information about dwellers and rooms.
        If False, displays only the count.
        """
        dwellers_info = ", ".join(d.full_name for d in self.dwellers) if verbose else self.population
        rooms_info = ", ".join([r.name for r in self.rooms]) if verbose else len(self.rooms)

        print(f"{self.name}:")
        print(f"Dwellers: {dwellers_info}")
        print(f"Rooms: {rooms_info}")
        print(f"Happiness: {self.happiness}")
        print(f"{self.power}, {self.food}, {self.water}")
        print(f"Bottle Caps: {self.bottle_caps}")

    def __str__(self):
        """
        Returns a string representation of the vault, including its name and the number of dwellers.

        :return: A string representation of the vault.
        """
        return f"{self.name} ({self.population})"
