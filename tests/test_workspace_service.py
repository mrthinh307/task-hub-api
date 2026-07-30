from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.enums import UserRole, WorkspaceAccessRole
from app.core.exceptions import EntityNotFoundError
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace_repository import (
    WorkspaceAccess,
    WorkspaceCreateData,
)
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace_service import WorkspaceService


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.create_calls: list[WorkspaceCreateData] = []
        self.access: WorkspaceAccess | None = None
        self.get_calls: list[tuple[UUID, UUID]] = []

    async def create(
        self,
        obj_in: WorkspaceCreateData,
        *,
        refresh: bool = True,
    ) -> Workspace:
        self.create_calls.append(obj_in)
        now = datetime.now(UTC)
        return Workspace(
            id=uuid4(),
            name=obj_in.name,
            owner_id=obj_in.owner_id,
            created_at=now,
            updated_at=now,
        )

    async def get_accessible_by_id(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceAccess | None:
        self.get_calls.append((workspace_id, user_id))
        return self.access


def make_user() -> User:
    return User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Workspace Owner",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_create_workspace_assigns_authenticated_user_as_owner() -> None:
    repo = FakeWorkspaceRepository()
    service = WorkspaceService(repo)  # type: ignore[arg-type]
    current_user = make_user()

    workspace = await service.create_workspace(
        current_user,
        WorkspaceCreate(name="Engineering"),
    )

    assert workspace.name == "Engineering"
    assert workspace.owner_id == current_user.id
    assert repo.create_calls == [
        WorkspaceCreateData(
            name="Engineering",
            owner_id=current_user.id,
        )
    ]


@pytest.mark.parametrize(
    "role",
    [
        WorkspaceAccessRole.OWNER,
        WorkspaceAccessRole.EDITOR,
        WorkspaceAccessRole.VIEWER,
    ],
)
@pytest.mark.asyncio
async def test_get_workspace_returns_effective_role(
    role: WorkspaceAccessRole,
) -> None:
    repo = FakeWorkspaceRepository()
    service = WorkspaceService(repo)  # type: ignore[arg-type]
    current_user = make_user()
    now = datetime.now(UTC)
    workspace = Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    repo.access = WorkspaceAccess(workspace=workspace, role=role)

    result = await service.get_workspace(workspace.id, current_user)

    assert result.id == workspace.id
    assert result.name == workspace.name
    assert result.owner_id == workspace.owner_id
    assert result.role is role
    assert repo.get_calls == [(workspace.id, current_user.id)]


@pytest.mark.asyncio
async def test_get_workspace_hides_missing_or_inaccessible_workspace() -> None:
    repo = FakeWorkspaceRepository()
    service = WorkspaceService(repo)  # type: ignore[arg-type]
    current_user = make_user()
    workspace_id = uuid4()

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.get_workspace(workspace_id, current_user)

    assert exc_info.value.details == {
        "entity": "Workspace",
        "id": str(workspace_id),
    }
    assert repo.get_calls == [(workspace_id, current_user.id)]
