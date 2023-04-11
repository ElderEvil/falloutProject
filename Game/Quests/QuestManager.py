class QuestManager:
    def __init__(self):
        self.quest_chains = {}

    def add_quest_chain(self, quest_chain):
        self.quest_chains[quest_chain.name] = quest_chain

    def complete_quest_step(self, quest_chain_name, quest_name, step_index):
        quest_chain = self.quest_chains[quest_chain_name]
        quest = next((q for q in quest_chain.quests if q.name == quest_name), None)
        if quest:
            step = quest.steps[step_index]
            step.is_completed = True

    def is_quest_step_completed(self, quest_chain_name, quest_name, step_index):
        quest_chain = self.quest_chains[quest_chain_name]
        quest = next((q for q in quest_chain.quests if q.name == quest_name), None)
        if quest:
            step = quest.steps[step_index]
            return step.is_completed
        return False

    def complete_quest(self, quest_chain_name, quest_name):
        quest_chain = self.quest_chains[quest_chain_name]
        quest = next((q for q in quest_chain.quests if q.name == quest_name), None)
        if quest:
            quest.is_completed = True

    def is_quest_completed(self, quest_chain_name, quest_name):
        quest_chain = self.quest_chains[quest_chain_name]
        quest = next((q for q in quest_chain.quests if q.name == quest_name), None)
        if quest:
            return quest.is_completed
        return False

    def get_quests(self):
        ...
