from enum import Enum


class Rarity(str, Enum):
    common = "common"
    rare = "rare"
    legendary = "legendary"


class Gender(str, Enum):
    male = "male"
    female = "female"
