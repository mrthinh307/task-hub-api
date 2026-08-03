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
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.comment import Comment
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.comment_repository import CommentCreateData
from app.repositories.workspace_repository import WorkspaceAccess
from app.schemas.comment import CommentCreate
from app.services.comment_service import CommentService


class FakeCommentRepository:
    def __init__(self) -> None:
        self.comments: dict[UUID, Comment] = {}
        self.create_calls: list[CommentCreateData] = []
        self.delete_calls: list[UUID] = []
        self.delete_result: bool | None = None

    async def create(
        self,
        obj_in: CommentCreateData,
        *,
        refresh: bool = True,
    ) -> Comment:
        self.create_calls.append(obj_in)
        now = datetime.now(UTC)
        comment = Comment(
            id=uuid4(),
            task_id=obj_in.task_id,
            author_id=obj_in.author_id,
            content=obj_in.content,
            created_at=now,
            updated_at=now,
        )
        self.comments[comment.id] = comment
        return comment

    async def get_by_id(self, comment_id: UUID) -> Comment | None:
        return self.comments.get(comment_id)

    async def delete(self, comment_id: UUID) -> bool:
        self.delete_calls.append(comment_id)
        if self.delete_result is not None:
            return self.delete_result
        return self.comments.pop(comment_id, None) is not None


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[UUID, Task] = {}

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return self.tasks.get(task_id)


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


def make_context(
    *,
    role: WorkspaceAccessRole = WorkspaceAccessRole.VIEWER,
) -> tuple[
    CommentService,
    FakeCommentRepository,
    FakeTaskRepository,
    FakeProjectRepository,
    FakeWorkspaceRepository,
    Task,
    User,
]:
    now = datetime.now(UTC)
    current_user = User(
        id=uuid4(),
        email="commenter@example.com",
        full_name="Task Commenter",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )
    workspace = Workspace(id=uuid4(), name="Engineering", owner_id=uuid4())
    project = Project(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Task Hub",
        description=None,
        status=ProjectStatus.ACTIVE,
    )
    task = Task(
        id=uuid4(),
        project_id=project.id,
        assignee_id=None,
        created_by=current_user.id,
        title="Implement comments",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_at=now,
        updated_at=now,
    )
    comment_repo = FakeCommentRepository()
    task_repo = FakeTaskRepository()
    task_repo.tasks[task.id] = task
    project_repo = FakeProjectRepository()
    project_repo.projects[project.id] = project
    workspace_repo = FakeWorkspaceRepository()
    workspace_repo.access = WorkspaceAccess(workspace=workspace, role=role)
    service = CommentService(
        comment_repo,  # type: ignore[arg-type]
        task_repo,  # type: ignore[arg-type]
        project_repo,  # type: ignore[arg-type]
        workspace_repo,  # type: ignore[arg-type]
    )
    return (
        service,
        comment_repo,
        task_repo,
        project_repo,
        workspace_repo,
        task,
        current_user,
    )


@pytest.mark.parametrize("role", list(WorkspaceAccessRole))
@pytest.mark.asyncio
async def test_workspace_members_can_add_comment(
    role: WorkspaceAccessRole,
) -> None:
    service, repo, _, _, _, task, user = make_context(role=role)

    comment = await service.add_comment(
        task.id,
        user,
        CommentCreate(content="Looks good"),
    )

    assert comment.task_id == task.id
    assert comment.author_id == user.id
    assert repo.create_calls == [
        CommentCreateData(
            task_id=task.id,
            author_id=user.id,
            content="Looks good",
        )
    ]


@pytest.mark.asyncio
async def test_add_comment_hides_inaccessible_task() -> None:
    service, repo, _, _, workspace_repo, task, user = make_context()
    workspace_repo.access = None

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.add_comment(task.id, user, CommentCreate(content="Hello"))

    assert exc_info.value.details == {"entity": "Task", "id": str(task.id)}
    assert repo.create_calls == []


@pytest.mark.asyncio
async def test_comment_author_can_delete_comment() -> None:
    service, repo, _, _, _, task, user = make_context()
    comment = await repo.create(
        CommentCreateData(
            task_id=task.id,
            author_id=user.id,
            content="Remove me",
        )
    )
    repo.create_calls.clear()

    await service.delete_comment(comment.id, user)

    assert repo.delete_calls == [comment.id]
    assert comment.id not in repo.comments


@pytest.mark.asyncio
async def test_non_author_cannot_delete_comment() -> None:
    service, repo, _, _, _, task, user = make_context()
    comment = await repo.create(
        CommentCreateData(
            task_id=task.id,
            author_id=uuid4(),
            content="Someone else's comment",
        )
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        await service.delete_comment(comment.id, user)

    assert exc_info.value.details == {"comment_id": str(comment.id)}
    assert repo.delete_calls == []


@pytest.mark.asyncio
async def test_delete_comment_hides_inaccessible_comment() -> None:
    service, repo, _, _, workspace_repo, task, user = make_context()
    comment = await repo.create(
        CommentCreateData(
            task_id=task.id,
            author_id=user.id,
            content="Private workspace comment",
        )
    )
    workspace_repo.access = None

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.delete_comment(comment.id, user)

    assert exc_info.value.details == {
        "entity": "Comment",
        "id": str(comment.id),
    }
    assert repo.delete_calls == []


@pytest.mark.asyncio
async def test_delete_missing_comment_returns_not_found() -> None:
    service, repo, _, _, _, _, user = make_context()
    comment_id = uuid4()

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.delete_comment(comment_id, user)

    assert exc_info.value.details == {
        "entity": "Comment",
        "id": str(comment_id),
    }
    assert repo.delete_calls == []


@pytest.mark.asyncio
async def test_delete_comment_handles_concurrent_deletion() -> None:
    service, repo, _, _, _, task, user = make_context()
    comment = await repo.create(
        CommentCreateData(
            task_id=task.id,
            author_id=user.id,
            content="Delete concurrently",
        )
    )
    repo.delete_result = False

    with pytest.raises(EntityNotFoundError):
        await service.delete_comment(comment.id, user)

    assert repo.delete_calls == [comment.id]
