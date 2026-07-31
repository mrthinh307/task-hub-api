from uuid import UUID

from app.core.enums import ProjectStatus, WorkspaceAccessRole
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.project import Project
from app.models.user import User
from app.repositories.project_repository import ProjectCreateData, ProjectRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.project import ProjectCreate


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        workspace_repo: WorkspaceRepository,
    ) -> None:
        self.project_repo = project_repo
        self.workspace_repo = workspace_repo

    async def create_project(
        self,
        workspace_id: UUID,
        current_user: User,
        payload: ProjectCreate,
    ) -> Project:
        access = await self.workspace_repo.get_accessible_by_id(
            workspace_id,
            current_user.id,
        )
        if access is None:
            raise EntityNotFoundError("Workspace", workspace_id)
        if access.role not in {
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        }:
            raise PermissionDeniedError(
                message="Viewer role cannot create projects in this workspace",
                details={
                    "workspace_id": str(workspace_id),
                    "required_roles": [
                        WorkspaceAccessRole.OWNER,
                        WorkspaceAccessRole.EDITOR,
                    ],
                },
            )

        return await self.project_repo.create(
            ProjectCreateData(
                workspace_id=workspace_id,
                name=payload.name,
                description=payload.description,
                status=ProjectStatus.ACTIVE,
            )
        )
