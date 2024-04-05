import json
import logging
from pathlib import Path
from typing import Type

from sqlmodel import SQLModel

from app.crud.base import CreateSchemaType
from app.schemas.common import Rarity, Gender, OutfitType
from app.schemas.dweller import DwellerCreateWithoutVaultID
from app.schemas.room import RoomCreate
from app.schemas.junk import JunkCreate
from app.schemas.outfit import OutfitCreate
from app.schemas.weapon import WeaponCreate


ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "data"


class StaticGameData:
    def __init__(self):
        # Dwellers
        # self.dwellers_legendary = self.parse_dweller_json(DATA_DIR / "dwellers/legendary.json")
        # self.dwellers_rare = self.parse_dweller_json(DATA_DIR / "dwellers/rare.json")

        # Items
        self.junk = self.load_data(DATA_DIR / "items/junk.json", JunkCreate)
        # self.outfits = self.parse_outfit_json(DATA_DIR / 'items/outfits/common.json')
        self.weapons = self.parse_weapon_json(DATA_DIR / "items/weapons.json")

        # Vault
        # self.rooms = self.load_data(DATA_DIR / 'data/vault/rooms.json', Room)

    def split_name(self, full_name: str) -> tuple[str, str]:
        first_name, _, last_name = full_name.partition(" ")
        return first_name, last_name

    def parse_dweller_json(self, file_path: Path) -> list[DwellerCreateWithoutVaultID]:
        with file_path.open("r") as file:
            dwellers_json = json.load(file)
            dwellers = []
            for dweller_data in dwellers_json:
                first_name, _, last_name = dweller_data.pop("name").partition(" ")
                dweller_data["first_name"] = first_name
                dweller_data["last_name"] = last_name
                dweller_data["gender"] = Gender.male
                dweller = DwellerCreateWithoutVaultID.model_validate(dweller_data)
                dwellers.append(dweller)
            return dwellers

    def parse_outfit_json(self, outfit_type: OutfitType) -> list[OutfitCreate]:
        type_path = outfit_type.value.lower().replace(" ", "_").replace("_outfit", "")
        file_path = DATA_DIR / "items/outfits" / f"{type_path}.json"
        with open(file_path) as file:
            outfits_json = json.load(file)
            outfits = []
            for outfit_data in outfits_json:
                stats = outfit_data["SPECIAL"]
                outfit_data.update(stats)
                outfit_data["outfit_type"] = OutfitType[outfit_type]

                outfit = OutfitCreate(**outfit_data)
                outfits.append(outfit)
            return outfits

    def parse_weapon_json(self, file_path: Path) -> list[WeaponCreate]:
        with open(file_path) as file:
            weapons_json = json.load(file)
            weapons = []
            for weapon_data in weapons_json:
                weapon = WeaponCreate(**weapon_data)
                weapons.append(weapon)

            return weapons

    def parse_room_json(self, file_path: Path) -> list[RoomCreate]:
        with open(file_path) as file:
            rooms_json = json.load(file)
            rooms = []
            for room_data in rooms_json:
                room = RoomCreate(**room_data)
                rooms.append(room)
            return rooms

    @staticmethod
    def load_data(file_path: Path, model: Type[SQLModel]) -> list[CreateSchemaType]:
        try:
            with file_path.open("r") as file:
                data_list = json.load(file)  # noqa: F841
                # return [model.model_validate(data, strict=False) for data in data_list]
        except json.JSONDecodeError:
            logging.exception(f"Invalid JSON format in {file_path}")
            return []
        except FileNotFoundError:
            logging.exception(f"File not found: {file_path}")
            return []


game_data_store = StaticGameData()
