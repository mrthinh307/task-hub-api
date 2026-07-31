from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.enums import ProjectStatus, UserRole, WorkspaceAccessRole
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.project_repository import ProjectCreateData
from app.repositories.workspace_repository import WorkspaceAccess
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService


class FakeProjectRepository:
    def __init__(self) -> None:
        self.create_calls: list[ProjectCreateData] = []

    async def create(
        self,
        obj_in: ProjectCreateData,
        *,
        refresh: bool = True,
    ) -> Project:
        self.create_calls.append(obj_in)
        now = datetime.now(UTC)
        return Project(
            id=uuid4(),
            workspace_id=obj_in.workspace_id,
            name=obj_in.name,
            description=obj_in.description,
            status=obj_in.status,
            created_at=now,
            updated_at=now,
        )


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.access: WorkspaceAccess | None = None
        self.get_calls: list[tuple[UUID, UUID]] = []

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
        email="member@example.com",
        full_name="Workspace Member",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def make_workspace(*, owner_id: UUID) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize(
    "role",
    [WorkspaceAccessRole.OWNER, WorkspaceAccessRole.EDITOR],
)
@pytest.mark.asyncio
async def test_create_project_allows_workspace_writers(
    role: WorkspaceAccessRole,
) -> None:
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project_repo = FakeProjectRepository()
    workspace_repo = FakeWorkspaceRepository()
    workspace_repo.access = WorkspaceAccess(workspace=workspace, role=role)
    service = ProjectService(project_repo, workspace_repo)  # type: ignore[arg-type]

    project = await service.create_project(
        workspace.id,
        current_user,
        ProjectCreate(name="Task Hub", description="API project"),
    )

    assert project.workspace_id == workspace.id
    assert project.status is ProjectStatus.ACTIVE
    assert workspace_repo.get_calls == [(workspace.id, current_user.id)]
    assert project_repo.create_calls == [
        ProjectCreateData(
            workspace_id=workspace.id,
            name="Task Hub",
            description="API project",
            status=ProjectStatus.ACTIVE,
        )
    ]


@pytest.mark.asyncio
async def test_create_project_rejects_viewer() -> None:
    current_user = make_user()
    workspace = make_workspace(owner_id=uuid4())
    project_repo = FakeProjectRepository()
    workspace_repo = FakeWorkspaceRepository()
    workspace_repo.access = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.VIEWER,
    )
    service = ProjectService(project_repo, workspace_repo)  # type: ignore[arg-type]

    with pytest.raises(PermissionDeniedError) as exc_info:
        await service.create_project(
            workspace.id,
            current_user,
            ProjectCreate(name="Task Hub"),
        )

    assert exc_info.value.details == {
        "workspace_id": str(workspace.id),
        "required_roles": [
            WorkspaceAccessRole.OWNER,
            WorkspaceAccessRole.EDITOR,
        ],
    }
    assert project_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_project_hides_missing_or_inaccessible_workspace() -> None:
    current_user = make_user()
    workspace_id = uuid4()
    project_repo = FakeProjectRepository()
    workspace_repo = FakeWorkspaceRepository()
    service = ProjectService(project_repo, workspace_repo)  # type: ignore[arg-type]

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.create_project(
            workspace_id,
            current_user,
            ProjectCreate(name="Task Hub"),
        )

    assert exc_info.value.details == {
        "entity": "Workspace",
        "id": str(workspace_id),
    }
    assert workspace_repo.get_calls == [(workspace_id, current_user.id)]
    assert project_repo.create_calls == []
