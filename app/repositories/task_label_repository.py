from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskLabel


class TaskLabelRepository:
    """Persistence operations for the Task-Label association."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, task_id: UUID, label_id: UUID) -> None:
        stmt = (
            insert(TaskLabel)
            .values(task_id=task_id, label_id=label_id)
            .on_conflict_do_nothing(constraint="uq_task_labels_task_label")
        )
        await self.session.execute(stmt)

    async def remove(self, task_id: UUID, label_id: UUID) -> None:
        await self.session.execute(
            delete(TaskLabel).where(
                TaskLabel.task_id == task_id,
                TaskLabel.label_id == label_id,
            )
        )
