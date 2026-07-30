from uuid import UUID

from app.core.exceptions import EntityNotFoundError
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace_repository import (
    WorkspaceCreateData,
    WorkspaceRepository,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetailResponse,
)


class WorkspaceService:
    def __init__(self, repo: WorkspaceRepository):
        self.repo = repo

    async def create_workspace(
        self,
        current_user: User,
        payload: WorkspaceCreate,
    ) -> Workspace:
        return await self.repo.create(
            WorkspaceCreateData(
                name=payload.name,
                owner_id=current_user.id,
            )
        )

    async def get_workspace(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> WorkspaceDetailResponse:
        access = await self.repo.get_accessible_by_id(
            workspace_id,
            current_user.id,
        )
        if access is None:
            raise EntityNotFoundError("Workspace", workspace_id)

        workspace = access.workspace
        return WorkspaceDetailResponse(
            id=workspace.id,
            name=workspace.name,
            owner_id=workspace.owner_id,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            role=access.role,
        )
