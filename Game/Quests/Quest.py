class QuestStep:
    def __init__(self, description: str, is_completed: bool = False):
        self.description = description
        self.is_completed = is_completed


class Quest:
    def __init__(self, name: str, steps: list[QuestStep]):
        self.name = name
        self.steps = steps
        self.is_completed = False


class QuestChain:
    def __init__(self, name: str, quests: list[Quest]):
        self.name = name
        self.quests = quests
        self.is_completed = False
