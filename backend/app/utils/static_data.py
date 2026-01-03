import json
import logging
from pathlib import Path

from app.crud.base import CreateSchemaType
from app.schemas.dweller import DwellerCreateWithoutVaultID
from app.schemas.junk import JunkCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.outfit import OutfitCreate
from app.schemas.quest import QuestChainJSON
from app.schemas.room import RoomCreateWithoutVaultID
from app.schemas.weapon import WeaponCreate

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "app" / "data"


class StaticGameData:
    def __init__(self):
        self._dwellers: list[DwellerCreateWithoutVaultID] | None = None
        self._rooms: list[RoomCreateWithoutVaultID] | None = None
        self._junk_items: list[JunkCreate] | None = None
        self._outfits: list[OutfitCreate] | None = None
        self._weapons: list[WeaponCreate] | None = None
        self._quests: list[QuestChainJSON] | None = None
        self._objectives: list[ObjectiveCreate] | None = None

    @property
    def dwellers(self) -> list[DwellerCreateWithoutVaultID]:
        if self._dwellers is None:
            rare = self.load_data(DATA_DIR / "dwellers/rare.json", DwellerCreateWithoutVaultID)
            legendary = self.load_data(DATA_DIR / "dwellers/legendary.json", DwellerCreateWithoutVaultID)
            self._dwellers = rare + legendary
        return self._dwellers

    @property
    def junk_items(self) -> list[JunkCreate]:
        if self._junk_items is None:
            self._junk_items = self.load_data(DATA_DIR / "items/junk.json", JunkCreate)
        return self._junk_items

    @property
    def outfits(self) -> list[OutfitCreate]:
        if self._outfits is None:
            common = self.load_data(DATA_DIR / "items/outfits/common.json", OutfitCreate)
            legendary = self.load_data(DATA_DIR / "items/outfits/legendary.json", OutfitCreate)
            power_armor = self.load_data(DATA_DIR / "items/outfits/power_armor.json", OutfitCreate)
            rare = self.load_data(DATA_DIR / "items/outfits/rare.json", OutfitCreate)
            tiered = self.load_data(DATA_DIR / "items/outfits/tiered.json", OutfitCreate)
            self._outfits = common + legendary + power_armor + rare + tiered
        return self._outfits

    @property
    def weapons(self) -> list[WeaponCreate]:
        if self._weapons is None:
            self._weapons = self.load_data(DATA_DIR / "items/weapons.json", WeaponCreate)
        return self._weapons

    @property
    def rooms(self) -> list[RoomCreateWithoutVaultID]:
        if self._rooms is None:
            self._rooms = self.load_data(DATA_DIR / "vault/rooms.json", RoomCreateWithoutVaultID)
        return self._rooms

    @property
    def quests(self) -> list[QuestChainJSON]:
        """Load all quest chains from JSON files."""
        if self._quests is None:
            from app.utils.load_quests import load_all_quest_chain_files

            try:
                self._quests = load_all_quest_chain_files(quest_dir=DATA_DIR / "quests")
            except Exception:
                logger.exception("Failed to load quest chains")
                self._quests = []
        return self._quests

    @property
    def objectives(self) -> list[ObjectiveCreate]:
        """Load all objectives from JSON files."""
        if self._objectives is None:
            objectives_dir = DATA_DIR / "objectives"
            all_objectives = []
            if objectives_dir.exists():
                for json_file in objectives_dir.glob("*.json"):
                    objectives_data = self.load_data(json_file, ObjectiveCreate)
                    all_objectives.extend(objectives_data)
                    logger.debug(
                        "Loaded objectives from file", extra={"file": json_file.name, "count": len(objectives_data)}
                    )
            self._objectives = all_objectives
            logger.info("Loaded all objectives", extra={"total_objectives": len(all_objectives)})
        return self._objectives

    @staticmethod
    def load_data(file_path: Path, model: type[CreateSchemaType]) -> list[CreateSchemaType]:
        try:
            with file_path.open("r") as file:
                data_list = json.load(file)
                return [model.model_validate(item) for item in data_list]
        except (json.JSONDecodeError, FileNotFoundError):
            logger.exception("Failed to load data", extra={"file_path": file_path})
            return []


game_data_store = StaticGameData()
