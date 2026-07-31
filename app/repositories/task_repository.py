from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

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


@dataclass(frozen=True, slots=True)
class TaskFilterData:
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    unassigned: bool = False
    created_by: UUID | None = None
    due_from: datetime | None = None
    due_to: datetime | None = None


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
        filters: TaskFilterData,
        offset: int,
        limit: int,
    ) -> TaskListResult:
        conditions: list[ColumnElement[bool]] = [Task.project_id == project_id]
        if filters.status is not None:
            conditions.append(Task.status == filters.status)
        if filters.priority is not None:
            conditions.append(Task.priority == filters.priority)
        if filters.unassigned:
            conditions.append(Task.assignee_id.is_(None))
        elif filters.assignee_id is not None:
            conditions.append(Task.assignee_id == filters.assignee_id)
        if filters.created_by is not None:
            conditions.append(Task.created_by == filters.created_by)
        if filters.due_from is not None:
            conditions.append(Task.due_date >= filters.due_from)
        if filters.due_to is not None:
            conditions.append(Task.due_date <= filters.due_to)

        count_result = await self.session.execute(
            select(func.count(Task.id)).where(*conditions)
        )
        total = count_result.scalar_one()

        tasks_result = await self.session.execute(
            select(Task)
            .where(*conditions)
            .order_by(Task.created_at.desc(), Task.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return TaskListResult(
            items=tasks_result.scalars().all(),
            total=total,
        )
