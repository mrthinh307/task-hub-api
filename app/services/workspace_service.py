from collections.abc import Sequence
from uuid import UUID

from app.core.enums import WorkspaceMemberRole
from app.core.exceptions import EntityNotFoundException
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, repo: WorkspaceRepository):
        self.repo = repo

    async def get_workspace_by_id(self, workspace_id: UUID) -> Workspace:
        workspace = await self.repo.get_by_id(workspace_id)
        if not workspace:
            raise EntityNotFoundException("Workspace", workspace_id)
        return workspace

    async def get_user_workspaces(self, user_id: UUID) -> Sequence[Workspace]:
        return await self.repo.get_user_workspaces(user_id)

    async def create_workspace(
        self,
        owner_id: UUID,
        workspace_in: WorkspaceCreate,
    ) -> Workspace:
        data = workspace_in.model_dump()
        data["owner_id"] = owner_id
        workspace = await self.repo.create(data)

        # Automatically add owner to workspace_members as OWNER
        await self.repo.add_member(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceMemberRole.OWNER,
        )
        return workspace

    async def update_workspace(
        self,
        workspace_id: UUID,
        workspace_in: WorkspaceUpdate,
    ) -> Workspace:
        workspace = await self.get_workspace_by_id(workspace_id)
        return await self.repo.update(workspace, workspace_in)

    async def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceMemberRole = WorkspaceMemberRole.VIEWER,
    ) -> WorkspaceMember:
        await self.get_workspace_by_id(workspace_id)
        return await self.repo.add_member(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )

    async def delete_workspace(self, workspace_id: UUID) -> bool:
        await self.get_workspace_by_id(workspace_id)
        return await self.repo.delete(workspace_id)
