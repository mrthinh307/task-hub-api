from collections.abc import Awaitable, Callable
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
    ArchivedTaskUpdateError,
    EntityNotFoundError,
    PermissionDeniedError,
    TaskLabelProjectMismatchError,
)
from app.models.label import Label
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceAccess
from app.services.task_label_service import TaskLabelService


class FakeTaskLabelRepository:
    def __init__(self) -> None:
        self.add_calls: list[tuple[UUID, UUID]] = []
        self.remove_calls: list[tuple[UUID, UUID]] = []

    async def add(self, task_id: UUID, label_id: UUID) -> None:
        self.add_calls.append((task_id, label_id))

    async def remove(self, task_id: UUID, label_id: UUID) -> None:
        self.remove_calls.append((task_id, label_id))


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[UUID, Task] = {}

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return self.tasks.get(task_id)


class FakeLabelRepository:
    def __init__(self) -> None:
        self.labels: dict[UUID, Label] = {}

    async def get_by_id(self, label_id: UUID) -> Label | None:
        return self.labels.get(label_id)


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.access: WorkspaceAccess | None = None

    async def get_accessible_by_id(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceAccess | None:
        return self.access


class FakeTaskListCache:
    def __init__(self) -> None:
        self.invalidate_calls: list[UUID] = []

    async def invalidate_project(self, project_id: UUID) -> None:
        self.invalidate_calls.append(project_id)


class FakePostCommitActions:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[], Awaitable[None]]] = []

    def add(self, callback: Callable[[], Awaitable[None]]) -> None:
        self.callbacks.append(callback)

    async def run(self) -> None:
        callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            await callback()


def make_user() -> User:
    return User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Task Label Editor",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def make_context(
    *,
    role: WorkspaceAccessRole = WorkspaceAccessRole.EDITOR,
    project_status: ProjectStatus = ProjectStatus.ACTIVE,
) -> tuple[
    TaskLabelService,
    FakeTaskLabelRepository,
    FakeTaskRepository,
    FakeLabelRepository,
    FakeProjectRepository,
    FakeWorkspaceRepository,
    FakeTaskListCache,
    FakePostCommitActions,
    Task,
    Label,
    Project,
    User,
]:
    now = datetime.now(UTC)
    current_user = make_user()
    workspace = Workspace(id=uuid4(), name="Engineering", owner_id=uuid4())
    project = Project(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Task Hub",
        description=None,
        status=project_status,
    )
    task = Task(
        id=uuid4(),
        project_id=project.id,
        assignee_id=None,
        created_by=current_user.id,
        title="Implement labels",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_at=now,
        updated_at=now,
    )
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
        created_at=now,
        updated_at=now,
    )
    task_label_repo = FakeTaskLabelRepository()
    task_repo = FakeTaskRepository()
    task_repo.tasks[task.id] = task
    label_repo = FakeLabelRepository()
    label_repo.labels[label.id] = label
    project_repo = FakeProjectRepository()
    project_repo.projects[project.id] = project
    workspace_repo = FakeWorkspaceRepository()
    workspace_repo.access = WorkspaceAccess(workspace=workspace, role=role)
    task_cache = FakeTaskListCache()
    post_commit = FakePostCommitActions()
    service = TaskLabelService(
        task_label_repo,  # type: ignore[arg-type]
        task_repo,  # type: ignore[arg-type]
        label_repo,  # type: ignore[arg-type]
        project_repo,  # type: ignore[arg-type]
        workspace_repo,  # type: ignore[arg-type]
        task_cache,  # type: ignore[arg-type]
        post_commit,  # type: ignore[arg-type]
    )
    return (
        service,
        task_label_repo,
        task_repo,
        label_repo,
        project_repo,
        workspace_repo,
        task_cache,
        post_commit,
        task,
        label,
        project,
        current_user,
    )


@pytest.mark.parametrize(
    "role",
    [WorkspaceAccessRole.OWNER, WorkspaceAccessRole.EDITOR],
)
@pytest.mark.asyncio
async def test_assign_label_is_idempotent_for_project_writers(
    role: WorkspaceAccessRole,
) -> None:
    context = make_context(role=role)
    service, repo, _, _, _, _, cache, post_commit, task, label, project, user = context

    await service.assign_label(task.id, label.id, user)
    await service.assign_label(task.id, label.id, user)

    assert repo.add_calls == [(task.id, label.id), (task.id, label.id)]
    assert cache.invalidate_calls == []
    await post_commit.run()
    assert cache.invalidate_calls == [project.id, project.id]


@pytest.mark.asyncio
async def test_remove_label_is_idempotent() -> None:
    context = make_context()
    service, repo, _, _, _, _, cache, post_commit, task, label, project, user = context

    await service.remove_label(task.id, label.id, user)
    await service.remove_label(task.id, label.id, user)

    assert repo.remove_calls == [(task.id, label.id), (task.id, label.id)]
    assert cache.invalidate_calls == []
    await post_commit.run()
    assert cache.invalidate_calls == [project.id, project.id]


@pytest.mark.parametrize("operation", ["assign", "remove"])
@pytest.mark.asyncio
async def test_task_label_mutations_reject_viewer(operation: str) -> None:
    context = make_context(role=WorkspaceAccessRole.VIEWER)
    service, repo, _, _, _, _, _, _, task, label, _, user = context

    with pytest.raises(PermissionDeniedError):
        if operation == "assign":
            await service.assign_label(task.id, label.id, user)
        else:
            await service.remove_label(task.id, label.id, user)

    assert repo.add_calls == []
    assert repo.remove_calls == []


@pytest.mark.parametrize("operation", ["assign", "remove"])
@pytest.mark.asyncio
async def test_task_label_mutations_reject_archived_project(operation: str) -> None:
    context = make_context(project_status=ProjectStatus.ARCHIVED)
    service, repo, _, _, _, _, _, _, task, label, _, user = context

    with pytest.raises(ArchivedTaskUpdateError):
        if operation == "assign":
            await service.assign_label(task.id, label.id, user)
        else:
            await service.remove_label(task.id, label.id, user)

    assert repo.add_calls == []
    assert repo.remove_calls == []


@pytest.mark.asyncio
async def test_assign_label_rejects_cross_project_label() -> None:
    context = make_context()
    service, repo, _, _, _, _, _, _, task, label, _, user = context
    label.project_id = uuid4()

    with pytest.raises(TaskLabelProjectMismatchError) as exc_info:
        await service.assign_label(task.id, label.id, user)

    assert exc_info.value.details == {
        "task_id": str(task.id),
        "label_id": str(label.id),
        "task_project_id": str(task.project_id),
        "label_project_id": str(label.project_id),
    }
    assert repo.add_calls == []


@pytest.mark.asyncio
async def test_assign_label_rejects_missing_label() -> None:
    context = make_context()
    service, repo, _, label_repo, _, _, _, _, task, label, _, user = context
    label_repo.labels.clear()

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.assign_label(task.id, label.id, user)

    assert exc_info.value.details == {"entity": "Label", "id": str(label.id)}
    assert repo.add_calls == []


@pytest.mark.asyncio
async def test_assign_label_hides_inaccessible_task() -> None:
    context = make_context()
    service, repo, _, _, _, workspace_repo, _, _, task, label, _, user = context
    workspace_repo.access = None

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.assign_label(task.id, label.id, user)

    assert exc_info.value.details == {"entity": "Task", "id": str(task.id)}
    assert repo.add_calls == []
