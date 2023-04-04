from Game.Quests.Quest import QuestState, Quest, QuestProgress


class QuestManager:
    def __init__(self):
        self.quests = []

    def create_quest(self, name, description, prerequisites):
        quest = Quest(name, description, prerequisites)
        self.quests.append(quest)
        quest.id = len(self.quests)
        return quest

    def add_quest(self, quest):
        if self.check_prerequisites(quest):
            self.quests.append(quest)
            quest.id = len(self.quests)
        else:
            print(f"Could not add quest '{quest.name}' due to unmet prerequisites.")

    def check_prerequisites(self, quest):
        for prerequisite_id in quest.prerequisites:
            prerequisite = next((q for q in self.quests if q.id == prerequisite_id), None)
            if prerequisite is None or prerequisite.state != QuestState.DONE:
                return False
        return True

    def show_quests(self):
        if not self.quests:
            print("No quests available.")
        else:
            print("Quests:")
            for quest in self.quests:
                print(f"- {quest}")

    def start_quest(self, quest_id, player_id):
        quest = next((q for q in self.quests if q.id == quest_id), None)
        if quest is None:
            print(f"Quest with ID {quest_id} not found.")
            return None
        if quest.state != QuestState.NOT_STARTED:
            print(f"Quest {quest.name} cannot be started because it is already {quest.state.name.lower()}.")
            return None
        quest.state = QuestState.IN_PROGRESS
        return QuestProgress(quest_id, player_id, QuestState.IN_PROGRESS)

    def complete_step(self, quest_id, player_id, step_id):
        quest = next((q for q in self.quests if q.id == quest_id), None)
        if quest is None:
            print(f"Quest with ID {quest_id} not found.")
            return False
        if quest.state != QuestState.IN_PROGRESS:
            print(f"Step {step_id} of quest {quest.name} cannot be completed because the quest is not in progress.")
            return False
        step = next((s for s in quest.steps if s.id == step_id), None)
        if step is None:
            print(f"Step with ID {step_id} not found.")
            return False
        if step.completed:
            print(f"Step {step_id} of quest {quest.name} is already completed.")
            return False
        step.completed = True
        quest.check_completion()
        return True

    def complete_quest(self, quest_id, player_id):
        quest = next((q for q in self.quests if q.id == quest_id), None)
        if quest is None:
            print(f"Quest with ID {quest_id} not found.")
            return False
        if quest.state != QuestState.IN_PROGRESS:
            print(f"Quest {quest.name} cannot be completed because it is not in progress.")
            return False
        all_steps_completed = all(step.completed for step in quest.steps)
        if not all_steps_completed:
            print(f"Quest {quest.name} cannot be completed because not all steps are completed.")
            return False
        quest.state = QuestState.DONE
        return True

    def get_player_quests(self, player_id):
        player_quests = []
        for quest in self.quests:
            if any(progress.player_id == player_id for progress in quest.progress):
                player_quests.append(quest)
        return player_quests
