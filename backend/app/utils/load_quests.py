import json
import logging
from pathlib import Path

from app.schemas.quest import QuestChainJSON

logger = logging.getLogger(__name__)


def load_quest_chain_from_json(file_path: str) -> QuestChainJSON:
    """
    Load a quest chain from a JSON file.

    Handles two formats:
    1. Single quest format: {"Quest name": "...", "Short description": "...", ...}
    2. Chain format: {"chain_id": "...", "quests": [{"quest_name": "...", ...}, ...]}

    Args:
        file_path: Path to the JSON file containing quest data

    Returns:
        QuestChainJSON with parsed quests
    """
    path = Path(file_path)
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    title = path.stem.replace("_", " ").title()
    if isinstance(data, dict) and "quests" in data:
        return QuestChainJSON.model_validate(
            {
                "title": data.get("chain_name", title),
                "chain_id": data.get("chain_id"),
                "chain_description": data.get("chain_description"),
                "quests": data["quests"],
            }
        )
    return QuestChainJSON.model_validate({"title": title, "quests": data if isinstance(data, list) else [data]})


def load_all_quest_chain_files(quest_dir: Path | None = None) -> list[QuestChainJSON]:
    """
    Load all quest chains from JSON files.

    Args:
        quest_dir: Directory containing quest JSON files.
                   If None, uses default DATA_DIR/quests location.

    Returns:
        List of QuestChainJSON objects
    """
    if quest_dir is None:
        # Use relative path from this file's location
        root_dir = Path(__file__).parent.parent.parent
        quest_dir = root_dir / "app" / "data" / "quests"

    quest_chains = []

    if not quest_dir.exists():
        logger.warning("Quest directory not found", extra={"path": str(quest_dir)})
        return quest_chains

    for json_file in quest_dir.rglob("*.json"):
        try:
            quest_chain = load_quest_chain_from_json(str(json_file))
            quest_chains.append(quest_chain)
            logger.debug(
                "Loaded quest chain from file", extra={"file": json_file.name, "quest_count": len(quest_chain.quests)}
            )
        except Exception:
            logger.exception("Failed to load quest chain", extra={"file": str(json_file)})

    logger.info("Loaded all quest chains", extra={"total_chains": len(quest_chains)})
    return quest_chains


if __name__ == "__main__":
    all_quest_chains = load_all_quest_chain_files()

    for quest_chain in all_quest_chains:
        logger.info("Loaded quest chain: %s", quest_chain.title, extra={"quest_count": len(quest_chain.quests)})
        for quest in quest_chain.quests:
            logger.debug("  - Quest: %s", quest.quest_name)
