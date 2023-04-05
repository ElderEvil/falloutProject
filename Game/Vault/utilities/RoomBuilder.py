from typing import Type

from Game.Vault.Rooms import RoomType, AbstractRoom
from Game.logger_settings import logger


class RoomBuilder:
    """
    A class for building rooms.

    :ivar filters: a dictionary containing filters to apply when building rooms
    :ivar rooms: a list of rooms built so far
    """

    def __init__(self):
        """
        Initializes a new RoomBuilder instance.
        """
        self.filters = {
            'name': None,
            'type': None,
            'population_required': 0,
            'ability': None
        }
        self.rooms = []

    @staticmethod
    def __get_final_subclasses(cls):
        """
        Return a list of classes that have no subclasses.
        """
        final_subclasses = []
        for subclass in cls.__subclasses__():
            if not subclass.__subclasses__():
                final_subclasses.append(subclass)
            else:
                final_subclasses.extend(RoomBuilder.__get_final_subclasses(subclass))
        return final_subclasses

    @property
    def all_rooms(self):
        return self.__get_final_subclasses(AbstractRoom)

    def get_by_name(self, name: str):
        for room in self.all_rooms:
            if room.name == name:
                return room

    def filter_by_name(self, name: str) -> 'RoomBuilder':
        """
        Adds a name filter to the room builder.

        :param name: the name to filter by
        :return: the modified RoomBuilder instance
        """
        self.filters['name'] = name
        return self

    def filter_by_type(self, room_type: RoomType) -> 'RoomBuilder':
        """
        Adds a room type filter to the room builder.

        :param room_type: the room type to filter by
        :return: the modified RoomBuilder instance
        """
        self.filters['type'] = room_type
        return self

    def filter_by_population_required(self, population_required: int) -> 'RoomBuilder':
        """
        Adds a population required filter to the room builder.

        :param population_required: the minimum population required to filter by
        :return: the modified RoomBuilder instance
        """
        self.filters['population_required'] = population_required
        return self

    def filter_by_ability(self, ability: str) -> 'RoomBuilder':
        """
        Adds an ability filter to the room builder.

        :param ability: the ability to filter by
        :return: the modified RoomBuilder instance
        """
        self.filters['ability'] = ability
        return self

    def match_filter(self, attr: str, value) -> bool:
        """
        Check if the given attribute matches the filter.

        :param attr: a string representing the attribute to be checked
        :param value: the value of the attribute to be checked
        :return: a boolean indicating whether the attribute matches the filter
        """
        if attr == "name":
            return self.filters[attr] in value
        elif attr == 'population_required':
            return value <= self.filters[attr]
        elif attr in {"type", "ability"}:
            return value == self.filters[attr]

        return False

    def build(self) -> list[Type[AbstractRoom]]:
        """
        Builds a list of rooms that match the current filters.

        :return: a list of rooms that match the current filters
        """

        self.rooms = [room for room in self.all_rooms if all(self.match_filter(attr, getattr(room, attr))
                                                             for attr in self.filters if
                                                             self.filters[attr] is not None)]
        filtered_rooms = self.rooms.copy()
        self.reset_filters()
        return filtered_rooms

    def reset_filters(self):
        """
        Resets all filters to their default values.
        """
        self.filters = {
            'name': None,
            'type': None,
            'population_required': 0,
            'ability': None
        }

    @staticmethod
    def build_room(room: Type[AbstractRoom]) -> AbstractRoom:
        """
        Builds a room of the given type.

        :param room: the type of room to build
        :return: a new instance of the specified room type
        """
        logger.info(f"Room {room.name} was built")

        return room()
