from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)
