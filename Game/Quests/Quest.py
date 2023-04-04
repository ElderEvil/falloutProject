from enum import Enum


class QuestState(Enum):
    NOT_STARTED = 1
    IN_PROGRESS = 2
    DONE = 3
    FAILED = 4


class QuestStep:
    def __init__(self, name):
        self.name = name
        self.completed = False


class Quest:
    def __init__(self, name, description, preconditions):
        self.id = None
        self.name = name
        self.description = description
        self.preconditions = preconditions
        self.state = QuestState.NOT_STARTED

    def __str__(self):
        return f"{self.id}: {self.name} ({self.state.name.lower()})"


class QuestProgress:
    def __init__(self, quest_id, player_id, state):
        self.quest_id = quest_id
        self.player_id = player_id
        self.state = state
