from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.enums import (
    ProjectStatus,
    TaskPriority,
    TaskStatus,
    UserRole,
    WorkspaceAccessRole,
)
from app.core.exceptions import (
    ArchivedProjectError,
    EntityNotFoundError,
    InactiveTaskAssigneeError,
    PermissionDeniedError,
    TaskAssigneeNotWorkspaceMemberError,
)
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.task_repository import (
    TaskCreateData,
    TaskFilterData,
    TaskListResult,
)
from app.repositories.workspace_repository import WorkspaceAccess
from app.schemas.task import TaskCreate, TaskFilters
from app.services.task_service import TaskService


class FakeTaskRepository:
    def __init__(self) -> None:
        self.create_calls: list[TaskCreateData] = []
        self.list_calls: list[tuple[UUID, TaskFilterData, int, int]] = []
        self.list_result = TaskListResult(items=[], total=0)

    async def create(
        self,
        obj_in: TaskCreateData,
        *,
        refresh: bool = True,
    ) -> Task:
        self.create_calls.append(obj_in)
        now = datetime.now(UTC)
        return Task(
            id=uuid4(),
            project_id=obj_in.project_id,
            assignee_id=obj_in.assignee_id,
            created_by=obj_in.created_by,
            title=obj_in.title,
            description=obj_in.description,
            status=obj_in.status,
            priority=obj_in.priority,
            due_date=obj_in.due_date,
            created_at=now,
            updated_at=now,
        )

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        filters: TaskFilterData,
        offset: int,
        limit: int,
    ) -> TaskListResult:
        self.list_calls.append((project_id, filters, offset, limit))
        return self.list_result


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}
        self.get_calls: list[UUID] = []

    async def get_by_id(self, project_id: UUID) -> Project | None:
        self.get_calls.append(project_id)
        return self.projects.get(project_id)


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.access_by_user: dict[UUID, WorkspaceAccess] = {}
        self.get_calls: list[tuple[UUID, UUID]] = []

    async def get_accessible_by_id(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceAccess | None:
        self.get_calls.append((workspace_id, user_id))
        return self.access_by_user.get(user_id)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.get_calls: list[UUID] = []

    async def get_by_id(self, user_id: UUID) -> User | None:
        self.get_calls.append(user_id)
        return self.users.get(user_id)


def make_user(*, active: bool = True) -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        full_name="Workspace Member",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=active,
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


def make_project(
    workspace_id: UUID,
    *,
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Task Hub",
        description=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def make_service() -> tuple[
    TaskService,
    FakeTaskRepository,
    FakeProjectRepository,
    FakeWorkspaceRepository,
    FakeUserRepository,
]:
    task_repo = FakeTaskRepository()
    project_repo = FakeProjectRepository()
    workspace_repo = FakeWorkspaceRepository()
    user_repo = FakeUserRepository()
    service = TaskService(
        task_repo,  # type: ignore[arg-type]
        project_repo,  # type: ignore[arg-type]
        workspace_repo,  # type: ignore[arg-type]
        user_repo,  # type: ignore[arg-type]
    )
    return service, task_repo, project_repo, workspace_repo, user_repo


@pytest.mark.parametrize(
    "role",
    [WorkspaceAccessRole.OWNER, WorkspaceAccessRole.EDITOR],
)
@pytest.mark.asyncio
async def test_create_task_allows_workspace_writers(
    role: WorkspaceAccessRole,
) -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=role,
    )
    due_date = datetime(2026, 8, 15, 10, tzinfo=UTC)

    task = await service.create_task(
        project.id,
        current_user,
        TaskCreate(
            title="Implement API",
            description="Create task endpoint",
            priority=TaskPriority.HIGH,
            due_date=due_date,
        ),
    )

    assert task.project_id == project.id
    assert task.created_by == current_user.id
    assert task.status is TaskStatus.TODO
    assert task_repo.create_calls == [
        TaskCreateData(
            project_id=project.id,
            assignee_id=None,
            created_by=current_user.id,
            title="Implement API",
            description="Create task endpoint",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            due_date=due_date,
        )
    ]


@pytest.mark.asyncio
async def test_create_task_allows_self_assignment_without_extra_lookup() -> None:
    service, task_repo, project_repo, workspace_repo, user_repo = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    await service.create_task(
        project.id,
        current_user,
        TaskCreate(title="Self assigned", assignee_id=current_user.id),
    )

    assert task_repo.create_calls[0].assignee_id == current_user.id
    assert user_repo.get_calls == []
    assert workspace_repo.get_calls == [(workspace.id, current_user.id)]


@pytest.mark.asyncio
async def test_create_task_allows_active_workspace_member_as_assignee() -> None:
    service, task_repo, project_repo, workspace_repo, user_repo = make_service()
    current_user = make_user()
    assignee = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    user_repo.users[assignee.id] = assignee
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )
    workspace_repo.access_by_user[assignee.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.VIEWER,
    )

    await service.create_task(
        project.id,
        current_user,
        TaskCreate(title="Assigned task", assignee_id=assignee.id),
    )

    assert task_repo.create_calls[0].assignee_id == assignee.id
    assert user_repo.get_calls == [assignee.id]
    assert workspace_repo.get_calls == [
        (workspace.id, current_user.id),
        (workspace.id, assignee.id),
    ]


@pytest.mark.asyncio
async def test_create_task_hides_missing_project() -> None:
    service, task_repo, _, _, _ = make_service()
    current_user = make_user()
    project_id = uuid4()

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.create_task(
            project_id,
            current_user,
            TaskCreate(title="Task"),
        )

    assert exc_info.value.details == {
        "entity": "Project",
        "id": str(project_id),
    }
    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_hides_inaccessible_project() -> None:
    service, task_repo, project_repo, _, _ = make_service()
    current_user = make_user()
    project = make_project(uuid4())
    project_repo.projects[project.id] = project

    with pytest.raises(EntityNotFoundError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task"),
        )

    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_rejects_viewer() -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=uuid4())
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.VIEWER,
    )

    with pytest.raises(PermissionDeniedError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task"),
        )

    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_rejects_archived_project() -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id, status=ProjectStatus.ARCHIVED)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    with pytest.raises(ArchivedProjectError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task"),
        )

    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_rejects_missing_assignee() -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    assignee_id = uuid4()
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    with pytest.raises(EntityNotFoundError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task", assignee_id=assignee_id),
        )

    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_rejects_inactive_assignee() -> None:
    service, task_repo, project_repo, workspace_repo, user_repo = make_service()
    current_user = make_user()
    assignee = make_user(active=False)
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    user_repo.users[assignee.id] = assignee
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    with pytest.raises(InactiveTaskAssigneeError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task", assignee_id=assignee.id),
        )

    assert task_repo.create_calls == []


@pytest.mark.asyncio
async def test_create_task_rejects_assignee_outside_workspace() -> None:
    service, task_repo, project_repo, workspace_repo, user_repo = make_service()
    current_user = make_user()
    assignee = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    user_repo.users[assignee.id] = assignee
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    with pytest.raises(TaskAssigneeNotWorkspaceMemberError):
        await service.create_task(
            project.id,
            current_user,
            TaskCreate(title="Task", assignee_id=assignee.id),
        )

    assert task_repo.create_calls == []


@pytest.mark.parametrize(
    "role",
    [
        WorkspaceAccessRole.OWNER,
        WorkspaceAccessRole.EDITOR,
        WorkspaceAccessRole.VIEWER,
    ],
)
@pytest.mark.asyncio
async def test_list_tasks_returns_paginated_tasks_for_all_workspace_roles(
    role: WorkspaceAccessRole,
) -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=role,
    )
    task = Task(
        id=uuid4(),
        project_id=project.id,
        assignee_id=None,
        created_by=current_user.id,
        title="Task",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    task_repo.list_result = TaskListResult(items=[task], total=21)

    result = await service.list_tasks(
        project.id,
        current_user,
        page=2,
        page_size=10,
        filters=TaskFilters(),
    )

    assert result.items[0].id == task.id
    assert result.page == 2
    assert result.page_size == 10
    assert result.total == 21
    assert result.total_pages == 3
    assert task_repo.list_calls == [
        (project.id, TaskFilterData(), 10, 10)
    ]


@pytest.mark.asyncio
async def test_list_tasks_allows_archived_project() -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id, status=ProjectStatus.ARCHIVED)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )

    result = await service.list_tasks(
        project.id,
        current_user,
        page=1,
        page_size=20,
        filters=TaskFilters(),
    )

    assert result.items == []
    assert result.total_pages == 0
    assert task_repo.list_calls == [
        (project.id, TaskFilterData(), 0, 20)
    ]


@pytest.mark.asyncio
async def test_list_tasks_hides_missing_or_inaccessible_project() -> None:
    service, task_repo, project_repo, _, _ = make_service()
    current_user = make_user()
    project = make_project(uuid4())
    project_repo.projects[project.id] = project

    with pytest.raises(EntityNotFoundError):
        await service.list_tasks(
            project.id,
            current_user,
            page=1,
            page_size=20,
            filters=TaskFilters(),
        )

    assert task_repo.list_calls == []


@pytest.mark.asyncio
async def test_list_tasks_forwards_filters_to_repository() -> None:
    service, task_repo, project_repo, workspace_repo, _ = make_service()
    current_user = make_user()
    workspace = make_workspace(owner_id=current_user.id)
    project = make_project(workspace.id)
    project_repo.projects[project.id] = project
    workspace_repo.access_by_user[current_user.id] = WorkspaceAccess(
        workspace=workspace,
        role=WorkspaceAccessRole.OWNER,
    )
    assignee_id = uuid4()
    creator_id = uuid4()
    due_from = datetime(2026, 8, 1, tzinfo=UTC)
    due_to = datetime(2026, 8, 31, 23, 59, tzinfo=UTC)
    filters = TaskFilters(
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assignee_id=assignee_id,
        created_by=creator_id,
        due_from=due_from,
        due_to=due_to,
    )

    await service.list_tasks(
        project.id,
        current_user,
        page=1,
        page_size=20,
        filters=filters,
    )

    assert task_repo.list_calls == [
        (
            project.id,
            TaskFilterData(
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH,
                assignee_id=assignee_id,
                created_by=creator_id,
                due_from=due_from,
                due_to=due_to,
            ),
            0,
            20,
        )
    ]
