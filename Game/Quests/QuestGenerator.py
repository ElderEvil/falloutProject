from Game.Quests.Quest import Quest, QuestChain, QuestStep


class QuestGenerator:
    def __init__(self):
        self.initial_prompt = ""
        self.quest_chain = None

    def generate_quest_chain(self, name, quest_number, depends_on=None, description=""):
        quest_steps = [QuestStep("Default")]
        quests = [Quest("name", quest_steps) for _ in range(quest_number)]

        self.quest_chain = QuestChain(name, quests)
