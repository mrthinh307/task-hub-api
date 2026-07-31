from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectStatus
from app.models.project import Project
from app.repositories.base_repository import CreateRepository, GetByIdRepository


class ProjectCreateData(BaseModel):
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus


class ProjectRepository(
    GetByIdRepository[Project],
    CreateRepository[Project, ProjectCreateData],
):
    """Persistence operations required by project features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)
