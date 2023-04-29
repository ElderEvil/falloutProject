from faker import Faker
from pydantic import validator
from sqlmodel import SQLModel

from utils.common import Gender, Rarity

fake = Faker()

LETTER_TO_STAT = {
    "S": "strength",
    "P": "perception",
    "A": "agility",
    "C": "charisma",
    "I": "intelligence",
    "L": "luck",
}


# _stats_range_by_rarity = {
#     Rarity.common: (1, 3),
#     Rarity.rare: (3, 6),
#     Rarity.legendary: (6, 10),
# }
#
#
# @validator('strength', 'perception', 'endurance', 'charisma', 'intelligence', 'agility', 'luck')
# def validate_stats(cls, v, values):
#     rarity = values['rarity']
#     stat_min, stat_max = cls._stats_range_by_rarity[rarity]
#     if not stat_min <= v <= stat_max:
#         raise ValueError(f"Invalid stat value for rarity {rarity}: {v}")
#     return v


class SPECIAL(SQLModel):
    strength: int
    perception: int
    endurance: int
    charisma: int
    intelligence: int
    agility: int
    luck: int


class Person(SPECIAL):
    gender: Gender = Gender.male
    first_name: str = ""
    last_name: str = ""
    rarity: Rarity = Rarity.common

    @validator("first_name")
    def validate_first_name(cls, v, values):
        if not v:
            gender = values.get("gender")
            return cls.get_gender_based_name(gender)
        return v

    @validator("last_name")
    def validate_last_name(cls, v):
        if not v:
            return fake.last_name()
        return v

    @staticmethod
    def get_gender_based_name(gender: Gender):
        if gender == Gender.male:
            return fake.first_name_male()
        else:  # noqa: RET505
            return fake.first_name_female()

    class Config:
        arbitrary_types_allowed = True
