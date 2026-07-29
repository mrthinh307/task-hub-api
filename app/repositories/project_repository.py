from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.base_repository import RepositoryBase


class ProjectRepository(RepositoryBase[Project]):
    """Placeholder repository; compose capabilities when project features are added."""

    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)
