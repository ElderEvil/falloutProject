from uuid import uuid4


def _get_unique_id(text):
    return f"{text}-{str(uuid4())[:8]}"


class Watcher:
    def __init__(self, vault, quest_chain):
        self.vault = vault
        self.quest_chain = quest_chain

    def watch(self):
        while True:
            self.quest_chain.update_progress(self.vault)
            # Add any additional logic you want to trigger when a step or quest is completed
