from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    EntityNotFoundError,
    InactiveWorkspaceMemberError,
    WorkspaceInviteeNotFoundError,
    WorkspaceMemberAlreadyExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceOwnerMembershipError,
    WorkspaceOwnerRemovalError,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_member_repository import WorkspaceMemberRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import (
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUserResponse,
)


def _is_unique_violation(exc: IntegrityError) -> bool:
    """Return whether PostgreSQL reported a unique-constraint violation."""
    return getattr(exc.orig, "sqlstate", None) == "23505"


class WorkspaceMembershipService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
        user_repo: UserRepository,
    ) -> None:
        self.workspace_repo = workspace_repo
        self.member_repo = member_repo
        self.user_repo = user_repo

    async def add_member(
        self,
        workspace_id: UUID,
        current_user: User,
        payload: WorkspaceMemberCreate,
    ) -> WorkspaceMemberResponse:
        workspace = await self.workspace_repo.get_owned_by_id(
            workspace_id,
            current_user.id,
        )
        if workspace is None:
            raise EntityNotFoundError("Workspace", workspace_id)

        email = str(payload.email).lower()
        member_user = await self.user_repo.get_by_email(email)
        if member_user is None:
            raise WorkspaceInviteeNotFoundError(email)
        if not member_user.is_active:
            raise InactiveWorkspaceMemberError(member_user.id)
        if member_user.id == workspace.owner_id:
            raise WorkspaceOwnerMembershipError(workspace.id, member_user.id)

        existing_member = await self.member_repo.get_by_workspace_and_user(
            workspace.id,
            member_user.id,
        )
        if existing_member is not None:
            raise WorkspaceMemberAlreadyExistsError(
                workspace.id,
                member_user.id,
            )

        try:
            member = await self.member_repo.create_member(
                workspace_id=workspace.id,
                user_id=member_user.id,
                role=payload.role,
            )
        except IntegrityError as exc:
            if not _is_unique_violation(exc):
                raise
            raise WorkspaceMemberAlreadyExistsError(
                workspace.id,
                member_user.id,
            ) from exc

        return WorkspaceMemberResponse(
            id=member.id,
            workspace_id=member.workspace_id,
            user=WorkspaceMemberUserResponse.model_validate(member_user),
            role=member.role,
            created_at=member.created_at,
            updated_at=member.updated_at,
        )

    async def remove_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        current_user: User,
    ) -> None:
        workspace = await self.workspace_repo.get_owned_by_id(
            workspace_id,
            current_user.id,
        )
        if workspace is None:
            raise EntityNotFoundError("Workspace", workspace_id)
        if user_id == workspace.owner_id:
            raise WorkspaceOwnerRemovalError(workspace.id, user_id)

        member = await self.member_repo.get_by_workspace_and_user(
            workspace.id,
            user_id,
        )
        if member is None:
            raise WorkspaceMemberNotFoundError(workspace.id, user_id)

        await self.member_repo.delete_member(member)
