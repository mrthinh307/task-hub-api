from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.base_repository import RepositoryBase


class WorkspaceRepository(RepositoryBase[Workspace]):
    def __init__(self, session: AsyncSession):
        super().__init__(Workspace, session)
