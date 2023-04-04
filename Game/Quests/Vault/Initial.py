from Game.Quests.QuestGenerator import QuestFactory
from Game.Quests.QuestManager import QuestManager

quest_system = QuestManager()
# create a QuestFactory object
factory = QuestFactory()

# create a dictionary representing the quest data
quest_data = {
    "name": "Test Quest",
    "description": "This is a test quest.",
    "preconditions": ["precondition1", "precondition2"],
    "steps": ["step1", "step2", "step3"]
}

# use the QuestFactory to create a new Quest object
new_quest = factory.create_quest(quest_data)

# add the new quest to the QuestManager
quest_system.add_quest(new_quest)
quest_system.show_quests()