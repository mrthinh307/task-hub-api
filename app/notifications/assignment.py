from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TaskAssignmentNotification:
    task_id: UUID
    task_title: str
    project_name: str
    assignee_email: str
    assignee_name: str
    assigned_by_name: str
    due_date: datetime | None


class AssignmentNotifier(Protocol):
    async def notify_task_assigned(
        self,
        notification: TaskAssignmentNotification,
    ) -> None: ...


class NoOpAssignmentNotifier:
    async def notify_task_assigned(
        self,
        notification: TaskAssignmentNotification,
    ) -> None:
        return None
