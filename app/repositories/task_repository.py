from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base_repository import BaseRepository


class TaskRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
