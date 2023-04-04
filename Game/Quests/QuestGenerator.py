from Game.Quests.Quest import Quest


class QuestGenerator:
    def __init__(self):
        self.quest_id_counter = 0

    def generate_quest(self, name, description, preconditions):
        quest = Quest(name, description, preconditions)
        quest.id = self.quest_id_counter
        self.quest_id_counter += 1
        return quest
