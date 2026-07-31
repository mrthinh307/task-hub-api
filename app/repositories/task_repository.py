from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
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


@dataclass(frozen=True, slots=True)
class TaskListResult:
    items: Sequence[Task]
    total: int


class TaskRepository(
    CreateRepository[Task, TaskCreateData],
):
    """Persistence operations required by task features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> TaskListResult:
        project_filter = Task.project_id == project_id

        count_result = await self.session.execute(
            select(func.count(Task.id)).where(project_filter)
        )
        total = count_result.scalar_one()

        tasks_result = await self.session.execute(
            select(Task)
            .where(project_filter)
            .order_by(Task.created_at.desc(), Task.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return TaskListResult(
            items=tasks_result.scalars().all(),
            total=total,
        )
