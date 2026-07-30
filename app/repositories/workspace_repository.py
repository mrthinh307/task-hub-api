from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.base_repository import CreateRepository


class WorkspaceCreateData(BaseModel):
    name: str
    owner_id: UUID


class WorkspaceRepository(
    CreateRepository[Workspace, WorkspaceCreateData],
):
    """Persistence operations required for workspace creation."""

    def __init__(self, session: AsyncSession):
        super().__init__(Workspace, session)
