from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkspaceMemberRole
from app.models.workspace import WorkspaceMember
from app.repositories.base_repository import CreateRepository


class WorkspaceMemberCreateData(BaseModel):
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceMemberRole


class WorkspaceMemberRepository(
    CreateRepository[WorkspaceMember, WorkspaceMemberCreateData],
):
    """Persistence operations required by workspace membership features."""

    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceMember, session)

    async def get_by_workspace_and_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        return await self.create(
            WorkspaceMemberCreateData(
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
            )
        )

    async def delete_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()
