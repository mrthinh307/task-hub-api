from app.repositories.task_repository import TaskRepository


class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo
