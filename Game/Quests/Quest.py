from typing import Any
from uuid import uuid4

from Game.Vault.Resources import ResourceType


def _get_unique_id(text):
    return f"{text}-{str(uuid4())[:8]}"


class QuestStep:
    def __init__(self, description: str, resource: Any = None, amount: int = 0, is_completed: bool = False):
        self.id = _get_unique_id(self.__class__.__name__)
        self.description = description
        self.resource = resource
        self.amount = amount
        self.is_completed = is_completed


class Quest:
    def __init__(self, name: str, steps: list[QuestStep], is_completed: bool = False):
        self.id = _get_unique_id(self.__class__.__name__)
        self.name = name
        self.steps = steps
        self.is_completed = is_completed

    def update_progress(self, vault):
        for step in self.steps:
            if step.is_completed:
                continue
            if step.resource in vault and vault[step.resource] >= step.amount:
                step.is_completed = True
                # Add any additional logic you want to trigger when a step is completed


class QuestChain:
    def __init__(self, name: str, quests: list[Quest], is_completed: bool = False):
        self.id = _get_unique_id(self.__class__.__name__)
        self.name = name
        self.quests = quests
        self.is_completed = is_completed

    def update_progress(self, vault):
        for quest in self.quests:
            if quest.is_completed:
                continue
            quest.update_progress(vault)
            if all(step.is_completed for step in quest.steps):
                quest.is_completed = True
                # Add any additional logic you want to trigger when a quest is completed


class Watcher:
    def __init__(self, vault, quest_chain):
        self.vault = vault
        self.quest_chain = quest_chain

    def watch(self):
        while True:
            self.quest_chain.update_progress(self.vault)
            # Add any additional logic you want to trigger when a step or quest is completed


qs = QuestStep("Description", ResourceType("Power", 100), 2)
q = Quest("QuestName", [qs])
qc = QuestChain("QuestChainName", [q])
print(qs.id)
print(q.id)
print(qc.id)
