import json
from pathlib import Path

from app.schemas.quest import QuestChainJSON, QuestJSON, QuestObjectiveJSON


def load_quest_chain_from_json(file_path: str) -> QuestChainJSON:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
        quests = [
            QuestJSON(
                quest_name=quest["Quest name"],
                long_description=quest["Long description"],
                quest_objective=[QuestObjectiveJSON(title=quest["Quest objective"])],
                short_description=quest["Short description"],
                requirements=quest["Requirements"],
                rewards=quest["Rewards"],
            )
            for quest in data
        ]

        return QuestChainJSON(title=path.stem.replace("_", " ").title(), quests=quests)
