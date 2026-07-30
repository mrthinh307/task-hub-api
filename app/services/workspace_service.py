from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace_repository import (
    WorkspaceCreateData,
    WorkspaceRepository,
)
from app.schemas.workspace import WorkspaceCreate


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
