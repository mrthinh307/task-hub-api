from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base_repository import CreateRepository


class TaskCreateData(BaseModel):
    project_id: UUID
    assignee_id: UUID | None
    created_by: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None


class TaskRepository(
    CreateRepository[Task, TaskCreateData],
):
    """Persistence operations required by task features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
