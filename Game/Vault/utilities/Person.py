import random
from enum import Enum

from faker import Faker

fake = Faker()

STAT_BY_LETTER = {
    "S": "strength",
    "P": "perception",
    "A": "agility",
    "C": "charisma",
    "I": "intelligence",
    "L": "luck",
}

SPECIAL_LETTERS = ("S", "P", "E", "C", "I", "A", "L")


class PersonRarity(Enum):
    COMMON = {'name': 'Common', 'stat_range': (1, 3)}
    RARE = {'name': 'Rare', 'stat_range': (3, 6)}
    LEGENDARY = {'name': 'Legendary', 'stat_range': (6, 10)}


class SPECIAL:
    def __init__(self, rarity: PersonRarity = PersonRarity.COMMON):
        self.__rarity = rarity
        self.__base_stats = {letter: random.randint(*self.__rarity.value['stat_range']) for letter in SPECIAL_LETTERS}
        self.strength, self.perception, self.endurance, self.charisma, self.intelligence, self.agility, self.luck = \
            self.base_stats.values()

    @property
    def rarity(self):
        return self.__rarity

    @property
    def base_stats(self):
        return self.__base_stats


class Person(SPECIAL):
    def __init__(self, gender: str = None, first_name: str = None, last_name: str = None,
                 rarity: PersonRarity = PersonRarity.COMMON):
        super().__init__(rarity)
        self.gender = gender or random.choice(["M", "F"])
        self.first_name = first_name or self.get_gender_based_name(self.gender)
        self.last_name = last_name or fake.last_name()
        self.full_name = f"{self.first_name} {self.last_name}"

    @staticmethod
    def get_gender_based_name(gender):
        return fake.first_name_male() if gender == "M" else fake.first_name_female()
