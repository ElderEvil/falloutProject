class Task:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, task: Task):
        self.tasks.append(task)

    def get_tasks(self) -> list[Task]:
        return self.tasks
