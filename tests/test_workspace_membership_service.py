from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.enums import UserRole, WorkspaceMemberRole
from app.core.exceptions import (
    EntityNotFoundError,
    InactiveWorkspaceMemberError,
    WorkspaceInviteeNotFoundError,
    WorkspaceMemberAlreadyExistsError,
    WorkspaceOwnerMembershipError,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_member_repository import WorkspaceMemberRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceMemberCreate
from app.services.workspace_membership_service import WorkspaceMembershipService


class FakeDatabaseError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate
        super().__init__(sqlstate)


class FakeWorkspaceRepository(WorkspaceRepository):
    def __init__(self, workspace: Workspace | None) -> None:
        self.workspace = workspace
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_owned_by_id(
        self,
        workspace_id: UUID,
        owner_id: UUID,
    ) -> Workspace | None:
        self.calls.append((workspace_id, owner_id))
        return self.workspace


class FakeUserRepository(UserRepository):
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.requested_emails: list[str] = []

    async def get_by_email(self, email: str) -> User | None:
        self.requested_emails.append(email)
        return self.user


class FakeWorkspaceMemberRepository(WorkspaceMemberRepository):
    def __init__(self) -> None:
        self.existing_member: WorkspaceMember | None = None
        self.create_error: IntegrityError | None = None
        self.created_member: WorkspaceMember | None = None
        self.lookup_calls: list[tuple[UUID, UUID]] = []

    async def get_by_workspace_and_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMember | None:
        self.lookup_calls.append((workspace_id, user_id))
        return self.existing_member

    async def create_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        if self.create_error is not None:
            raise self.create_error

        now = datetime.now(UTC)
        self.created_member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            created_at=now,
            updated_at=now,
        )
        return self.created_member


def make_user(
    *,
    email: str,
    is_active: bool = True,
) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Example User",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=is_active,
    )


def make_workspace(owner: User) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=owner.id,
        created_at=now,
        updated_at=now,
    )


def make_service(
    workspace: Workspace | None,
    user: User | None,
) -> tuple[
    WorkspaceMembershipService,
    FakeWorkspaceRepository,
    FakeWorkspaceMemberRepository,
    FakeUserRepository,
]:
    workspace_repo = FakeWorkspaceRepository(workspace)
    member_repo = FakeWorkspaceMemberRepository()
    user_repo = FakeUserRepository(user)
    service = WorkspaceMembershipService(workspace_repo, member_repo, user_repo)
    return service, workspace_repo, member_repo, user_repo


@pytest.mark.asyncio
async def test_add_member_creates_membership_and_returns_user_summary() -> None:
    owner = make_user(email="owner@example.com")
    member_user = make_user(email="member@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, user_repo = make_service(workspace, member_user)

    result = await service.add_member(
        workspace.id,
        owner,
        WorkspaceMemberCreate(
            email="MEMBER@example.com",
            role=WorkspaceMemberRole.EDITOR,
        ),
    )

    assert user_repo.requested_emails == ["member@example.com"]
    assert member_repo.lookup_calls == [(workspace.id, member_user.id)]
    assert result.workspace_id == workspace.id
    assert result.user.id == member_user.id
    assert result.user.email == member_user.email
    assert result.user.full_name == member_user.full_name
    assert result.role is WorkspaceMemberRole.EDITOR
    assert member_repo.created_member is not None
    assert member_repo.created_member.user_id == member_user.id


@pytest.mark.asyncio
async def test_add_member_hides_workspace_from_non_owner() -> None:
    current_user = make_user(email="viewer@example.com")
    member_user = make_user(email="member@example.com")
    workspace_id = uuid4()
    service, _, member_repo, user_repo = make_service(None, member_user)

    with pytest.raises(EntityNotFoundError):
        await service.add_member(
            workspace_id,
            current_user,
            WorkspaceMemberCreate(
                email=member_user.email,
                role=WorkspaceMemberRole.VIEWER,
            ),
        )

    assert user_repo.requested_emails == []
    assert member_repo.lookup_calls == []


@pytest.mark.asyncio
async def test_add_member_rejects_unknown_user() -> None:
    owner = make_user(email="owner@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, None)

    with pytest.raises(WorkspaceInviteeNotFoundError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email="missing@example.com",
                role=WorkspaceMemberRole.VIEWER,
            ),
        )

    assert member_repo.lookup_calls == []


@pytest.mark.asyncio
async def test_add_member_rejects_inactive_user() -> None:
    owner = make_user(email="owner@example.com")
    member_user = make_user(email="member@example.com", is_active=False)
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, member_user)

    with pytest.raises(InactiveWorkspaceMemberError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email=member_user.email,
                role=WorkspaceMemberRole.VIEWER,
            ),
        )

    assert member_repo.lookup_calls == []


@pytest.mark.asyncio
async def test_add_member_rejects_workspace_owner() -> None:
    owner = make_user(email="owner@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, owner)

    with pytest.raises(WorkspaceOwnerMembershipError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email=owner.email,
                role=WorkspaceMemberRole.EDITOR,
            ),
        )

    assert member_repo.lookup_calls == []


@pytest.mark.asyncio
async def test_add_member_rejects_existing_membership() -> None:
    owner = make_user(email="owner@example.com")
    member_user = make_user(email="member@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, member_user)
    member_repo.existing_member = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=member_user.id,
        role=WorkspaceMemberRole.VIEWER,
    )

    with pytest.raises(WorkspaceMemberAlreadyExistsError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email=member_user.email,
                role=WorkspaceMemberRole.EDITOR,
            ),
        )

    assert member_repo.created_member is None


@pytest.mark.asyncio
async def test_add_member_maps_unique_race_to_conflict() -> None:
    owner = make_user(email="owner@example.com")
    member_user = make_user(email="member@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, member_user)
    member_repo.create_error = IntegrityError(
        statement=None,
        params=None,
        orig=FakeDatabaseError("23505"),
    )

    with pytest.raises(WorkspaceMemberAlreadyExistsError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email=member_user.email,
                role=WorkspaceMemberRole.EDITOR,
            ),
        )


@pytest.mark.asyncio
async def test_add_member_does_not_mask_other_integrity_errors() -> None:
    owner = make_user(email="owner@example.com")
    member_user = make_user(email="member@example.com")
    workspace = make_workspace(owner)
    service, _, member_repo, _ = make_service(workspace, member_user)
    member_repo.create_error = IntegrityError(
        statement=None,
        params=None,
        orig=FakeDatabaseError("23503"),
    )

    with pytest.raises(IntegrityError):
        await service.add_member(
            workspace.id,
            owner,
            WorkspaceMemberCreate(
                email=member_user.email,
                role=WorkspaceMemberRole.EDITOR,
            ),
        )
