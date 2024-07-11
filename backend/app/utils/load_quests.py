import json
from pathlib import Path

from app.schemas.quest import QuestChainJSON, QuestJSON, QuestObjectiveJSON


def load_quest_chain_from_json(file_path: str) -> QuestChainJSON:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
        if not isinstance(data, list):
            data = [data]
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


def load_all_quest_chain_files() -> list[QuestChainJSON]:
    directory_path = "/data/quests"
    directory = Path(directory_path)
    quest_chains = []

    for json_file in directory.rglob("*.json"):
        quest_chain = load_quest_chain_from_json(json_file)
        quest_chains.append(quest_chain)

    return quest_chains


if __name__ == "__main__":
    all_quest_chains = load_all_quest_chain_files()

    for quest_chain in all_quest_chains:
        print(f"Loaded quest chain: {quest_chain.title}")
        for quest in quest_chain.quests:
            print(f"  - Quest: {quest.quest_name}")
