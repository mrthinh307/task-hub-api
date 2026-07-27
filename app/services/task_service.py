from collections.abc import Sequence
from uuid import UUID

from app.core.enums import TaskPriority, TaskStatus
from app.core.exceptions import EntityNotFoundException
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    async def get_task_by_id(self, task_id: UUID) -> Task:
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise EntityNotFoundException("Task", task_id)
        return task

    async def get_tasks(
        self,
        project_id: UUID | None = None,
        assignee_id: UUID | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Task]:
        return await self.repo.get_filtered(
            project_id=project_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            skip=skip,
            limit=limit,
        )

    async def create_task(self, task_in: TaskCreate) -> Task:
        return await self.repo.create(task_in)

    async def update_task(
        self,
        task_id: UUID,
        task_in: TaskUpdate,
    ) -> Task:
        task = await self.get_task_by_id(task_id)
        return await self.repo.update(task, task_in)

    async def delete_task(self, task_id: UUID) -> bool:
        await self.get_task_by_id(task_id)
        return await self.repo.delete(task_id)
