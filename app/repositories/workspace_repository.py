from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkspaceAccessRole, WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base_repository import CreateRepository


class WorkspaceCreateData(BaseModel):
    name: str
    owner_id: UUID


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    workspace: Workspace
    role: WorkspaceAccessRole


class WorkspaceRepository(
    CreateRepository[Workspace, WorkspaceCreateData],
):
    """Persistence operations required by workspace features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Workspace, session)

    async def get_accessible_by_id(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceAccess | None:
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .outerjoin(
                WorkspaceMember,
                and_(
                    WorkspaceMember.workspace_id == Workspace.id,
                    WorkspaceMember.user_id == user_id,
                ),
            )
            .where(
                Workspace.id == workspace_id,
                or_(
                    Workspace.owner_id == user_id,
                    WorkspaceMember.user_id == user_id,
                ),
            )
        )
        result = await self.session.execute(stmt)
        row = result.tuples().one_or_none()
        if row is None:
            return None

        workspace, membership_role = row
        if workspace.owner_id == user_id:
            role = WorkspaceAccessRole.OWNER
        elif membership_role is WorkspaceMemberRole.EDITOR:
            role = WorkspaceAccessRole.EDITOR
        elif membership_role is WorkspaceMemberRole.VIEWER:
            role = WorkspaceAccessRole.VIEWER
        else:
            return None

        return WorkspaceAccess(workspace=workspace, role=role)
