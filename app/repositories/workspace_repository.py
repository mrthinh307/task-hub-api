from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base_repository import BaseRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceRepository(BaseRepository[Workspace, WorkspaceCreate, WorkspaceUpdate]):
    def __init__(self, session: AsyncSession):
        super().__init__(Workspace, session)

    async def get_user_workspaces(self, user_id: UUID) -> Sequence[Workspace]:
        """Get all workspaces owned by or joined by the user."""
        stmt = (
            select(Workspace)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.id,
                isouter=True,
            )
            .where(
                (Workspace.owner_id == user_id) | (WorkspaceMember.user_id == user_id)
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceMemberRole = WorkspaceMemberRole.VIEWER,
    ) -> WorkspaceMember:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member
