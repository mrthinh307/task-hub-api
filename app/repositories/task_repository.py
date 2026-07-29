from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base_repository import RepositoryBase


class TaskRepository(RepositoryBase[Task]):
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
