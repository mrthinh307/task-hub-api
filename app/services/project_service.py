from collections.abc import Sequence
from uuid import UUID

from app.core.exceptions import EntityNotFoundException
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self.repo = repo

    async def get_project_by_id(self, project_id: UUID) -> Project:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def get_workspace_projects(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Project]:
        return await self.repo.get_by_workspace(
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )

    async def create_project(self, project_in: ProjectCreate) -> Project:
        return await self.repo.create(project_in)

    async def update_project(
        self,
        project_id: UUID,
        project_in: ProjectUpdate,
    ) -> Project:
        project = await self.get_project_by_id(project_id)
        return await self.repo.update(project, project_in)

    async def delete_project(self, project_id: UUID) -> bool:
        await self.get_project_by_id(project_id)
        return await self.repo.delete(project_id)
