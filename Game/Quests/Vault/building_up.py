from Game.Quests.Quest import Quest, QuestChain, QuestStep
from Game.Quests.QuestManager import QuestManager

# Quest 1
quest1_steps = [
    QuestStep("Build a Power generator"),
    QuestStep("Assign 2 Dwellers to the Power generator"),
    QuestStep("Collect 500 Power"),
]
quest1 = Quest("Build the Power generator", quest1_steps)

# Quest 2
quest2_steps = [
    QuestStep("Build a Kitchen"),
    QuestStep("Assign 2 Dwellers to the Kitchen"),
    QuestStep("Collect 500 Food"),
]
quest2 = Quest("Build the Kitchen", quest2_steps)

# Quest 3
quest3_steps = [
    QuestStep("Build a Water Treatment Room"),
    QuestStep("Assign 2 Dwellers to the Water Treatment Room"),
    QuestStep("Collect 500 Water"),
]
quest3 = Quest("Build the Water Treatment Room", quest3_steps)

# Quest chain
quest_chain = QuestChain("Building Up", [quest1, quest2, quest3])

# Add the quest to the Quest Manager
quest_manager = QuestManager()
quest_manager.add_quest_chain(quest_chain)

# Shorter version

room_resource = {
    "Power generator": "Power",
    "Kitchen": "Food",
    "Water Treatment": "Water",
}
quests = []
for room, resource in room_resource.items():
    quest_steps = [
        QuestStep(f"Build a {room}"),
        QuestStep(f"Assign 2 Dwellers to the {room}"),
        QuestStep(f"Collect 500 {resource}")
    ]
    q = Quest(f"Build a {room}", quest_steps)
    quests.append(q)
quest_chain = QuestChain("Building Up", quests)
