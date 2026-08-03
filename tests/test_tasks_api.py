from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_task_service
from app.core.enums import TaskPriority, TaskStatus, UserRole
from app.core.exceptions import (
    ArchivedProjectError,
    ArchivedTaskDeleteError,
    ArchivedTaskUpdateError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskCreate,
    TaskFilters,
    TaskPageResponse,
    TaskResponse,
    TaskUpdate,
)


class FakeTaskService:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, User, TaskCreate]] = []
        self.delete_calls: list[tuple[UUID, User]] = []
        self.update_calls: list[tuple[UUID, User, TaskUpdate]] = []
        self.list_calls: list[tuple[UUID, User, int, int, TaskFilters]] = []
        self.list_result = TaskPageResponse(
            items=[],
            page=1,
            page_size=20,
            total=0,
            total_pages=0,
        )
        self.error: Exception | None = None

    async def create_task(
        self,
        project_id: UUID,
        current_user: User,
        payload: TaskCreate,
    ) -> Task:
        self.calls.append((project_id, current_user, payload))
        if self.error is not None:
            raise self.error

        now = datetime.now(UTC)
        return Task(
            id=uuid4(),
            project_id=project_id,
            assignee_id=payload.assignee_id,
            created_by=current_user.id,
            title=payload.title,
            description=payload.description,
            status=TaskStatus.TODO,
            priority=payload.priority,
            due_date=payload.due_date,
            created_at=now,
            updated_at=now,
        )

    async def list_tasks(
        self,
        project_id: UUID,
        current_user: User,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> TaskPageResponse:
        self.list_calls.append(
            (project_id, current_user, page, page_size, filters)
        )
        if self.error is not None:
            raise self.error
        return self.list_result

    async def update_task(
        self,
        task_id: UUID,
        current_user: User,
        payload: TaskUpdate,
    ) -> Task:
        self.update_calls.append((task_id, current_user, payload))
        if self.error is not None:
            raise self.error

        now = datetime.now(UTC)
        update_data = payload.model_dump(exclude_unset=True)
        return Task(
            id=task_id,
            project_id=uuid4(),
            assignee_id=update_data.get("assignee_id", uuid4()),
            created_by=current_user.id,
            title=update_data.get("title", "Existing task"),
            description=update_data.get("description", "Existing description"),
            status=update_data.get("status", TaskStatus.TODO),
            priority=update_data.get("priority", TaskPriority.MEDIUM),
            due_date=update_data.get("due_date", now),
            created_at=now,
            updated_at=now,
        )

    async def delete_task(
        self,
        task_id: UUID,
        current_user: User,
    ) -> None:
        self.delete_calls.append((task_id, current_user))
        if self.error is not None:
            raise self.error


def make_user() -> User:
    return User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Task Editor",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeTaskService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_task_service] = lambda: service
    return TestClient(app)


def test_create_task_returns_created_task() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()
    assignee_id = uuid4()

    response = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={
            "title": "  Implement API  ",
            "description": "Create task endpoint",
            "assignee_id": str(assignee_id),
            "priority": "HIGH",
            "due_date": "2026-08-15T17:00:00+07:00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "project_id": str(project_id),
        "assignee_id": str(assignee_id),
        "created_by": str(current_user.id),
        "title": "Implement API",
        "description": "Create task endpoint",
        "status": "TODO",
        "priority": "HIGH",
        "due_date": "2026-08-15T17:00:00+07:00",
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }
    assert service.calls == [
        (
            project_id,
            current_user,
            TaskCreate(
                title="Implement API",
                description="Create task endpoint",
                assignee_id=assignee_id,
                priority=TaskPriority.HIGH,
                due_date=datetime.fromisoformat("2026-08-15T17:00:00+07:00"),
            ),
        )
    ]


def test_create_task_uses_optional_defaults() -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/tasks",
        json={"title": "Task"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["assignee_id"] is None
    assert body["description"] is None
    assert body["priority"] == "MEDIUM"
    assert body["status"] == "TODO"
    assert body["due_date"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "   "},
        {"title": "x" * 256},
        {"title": "Task", "priority": "INVALID"},
        {"title": "Task", "due_date": "2026-08-15T17:00:00"},
        {"title": "Task", "status": "DONE"},
        {"title": "Task", "project_id": str(uuid4())},
        {"title": "Task", "created_by": str(uuid4())},
        {"title": "Task", "extra": True},
    ],
)
def test_create_task_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/tasks",
        json=payload,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_create_task_rejects_invalid_project_id() -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        "/api/v1/projects/not-a-uuid/tasks",
        json={"title": "Task"},
    )

    assert response.status_code == 422
    assert service.calls == []


def test_create_task_requires_authentication() -> None:
    app = create_app()
    service = FakeTaskService()
    app.dependency_overrides[get_task_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/tasks",
        json={"title": "Task"},
    )

    assert response.status_code == 401
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            PermissionDeniedError(
                message="Viewer role cannot create tasks in this project"
            ),
            403,
        ),
        (EntityNotFoundError("Project", uuid4()), 404),
        (ArchivedProjectError(uuid4()), 409),
    ],
)
def test_create_task_maps_domain_errors(
    error: Exception,
    expected_status: int,
) -> None:
    service = FakeTaskService()
    service.error = error
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/tasks",
        json={"title": "Task"},
    )

    assert response.status_code == expected_status


def test_update_task_returns_updated_task() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    task_id = uuid4()

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "title": "  Review cache  ",
            "description": None,
            "assignee_id": None,
            "status": "IN_REVIEW",
            "priority": "HIGH",
            "due_date": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(task_id)
    assert body["title"] == "Review cache"
    assert body["description"] is None
    assert body["assignee_id"] is None
    assert body["status"] == "IN_REVIEW"
    assert body["priority"] == "HIGH"
    assert body["due_date"] is None
    assert service.update_calls == [
        (
            task_id,
            current_user,
            TaskUpdate(
                title="Review cache",
                description=None,
                assignee_id=None,
                status=TaskStatus.IN_REVIEW,
                priority=TaskPriority.HIGH,
                due_date=None,
            ),
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"title": "   "},
        {"title": "x" * 256},
        {"status": None},
        {"status": "INVALID"},
        {"priority": None},
        {"priority": "INVALID"},
        {"due_date": "2026-08-15T17:00:00"},
        {"project_id": str(uuid4())},
        {"created_by": str(uuid4())},
        {"extra": True},
    ],
)
def test_update_task_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.patch(
        f"/api/v1/tasks/{uuid4()}",
        json=payload,
    )

    assert response.status_code == 422
    assert service.update_calls == []


def test_update_task_rejects_invalid_task_id() -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.patch(
        "/api/v1/tasks/not-a-uuid",
        json={"title": "Task"},
    )

    assert response.status_code == 422
    assert service.update_calls == []


def test_update_task_requires_authentication() -> None:
    app = create_app()
    service = FakeTaskService()
    app.dependency_overrides[get_task_service] = lambda: service
    client = TestClient(app)

    response = client.patch(
        f"/api/v1/tasks/{uuid4()}",
        json={"title": "Task"},
    )

    assert response.status_code == 401
    assert service.update_calls == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            PermissionDeniedError(
                message="Viewer role cannot update tasks in this project"
            ),
            403,
        ),
        (EntityNotFoundError("Task", uuid4()), 404),
        (ArchivedTaskUpdateError(uuid4(), uuid4()), 409),
    ],
)
def test_update_task_maps_domain_errors(
    error: Exception,
    expected_status: int,
) -> None:
    service = FakeTaskService()
    service.error = error
    client = create_authenticated_client(make_user(), service)

    response = client.patch(
        f"/api/v1/tasks/{uuid4()}",
        json={"title": "Task"},
    )

    assert response.status_code == expected_status


def test_delete_task_returns_no_content() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    task_id = uuid4()

    response = client.delete(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.delete_calls == [(task_id, current_user)]


def test_delete_task_rejects_invalid_task_id() -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.delete("/api/v1/tasks/not-a-uuid")

    assert response.status_code == 422
    assert service.delete_calls == []


def test_delete_task_requires_authentication() -> None:
    app = create_app()
    service = FakeTaskService()
    app.dependency_overrides[get_task_service] = lambda: service
    client = TestClient(app)

    response = client.delete(f"/api/v1/tasks/{uuid4()}")

    assert response.status_code == 401
    assert service.delete_calls == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            PermissionDeniedError(
                message="Viewer role cannot delete tasks in this project"
            ),
            403,
        ),
        (EntityNotFoundError("Task", uuid4()), 404),
        (ArchivedTaskDeleteError(uuid4(), uuid4()), 409),
    ],
)
def test_delete_task_maps_domain_errors(
    error: Exception,
    expected_status: int,
) -> None:
    service = FakeTaskService()
    service.error = error
    client = create_authenticated_client(make_user(), service)

    response = client.delete(f"/api/v1/tasks/{uuid4()}")

    assert response.status_code == expected_status


def test_list_tasks_returns_default_paginated_response() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()
    now = datetime.now(UTC)
    task = Task(
        id=uuid4(),
        project_id=project_id,
        assignee_id=None,
        created_by=current_user.id,
        title="Newest task",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_at=now,
        updated_at=now,
    )
    service.list_result = TaskPageResponse(
        items=[TaskResponse.model_validate(task)],
        page=1,
        page_size=20,
        total=1,
        total_pages=1,
    )

    response = client.get(f"/api/v1/projects/{project_id}/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == str(task.id)
    assert body["items"][0]["title"] == "Newest task"
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] == 1
    assert body["total_pages"] == 1
    assert service.list_calls == [
        (project_id, current_user, 1, 20, TaskFilters())
    ]


def test_list_tasks_forwards_custom_pagination() -> None:
    current_user = make_user()
    service = FakeTaskService()
    service.list_result = TaskPageResponse(
        items=[],
        page=3,
        page_size=5,
        total=11,
        total_pages=3,
    )
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()

    response = client.get(
        f"/api/v1/projects/{project_id}/tasks",
        params={"page": 3, "page_size": 5},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 3,
        "page_size": 5,
        "total": 11,
        "total_pages": 3,
    }
    assert service.list_calls == [
        (project_id, current_user, 3, 5, TaskFilters())
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"page": "invalid"},
    ],
)
def test_list_tasks_rejects_invalid_pagination(
    params: dict[str, object],
) -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.get(
        f"/api/v1/projects/{uuid4()}/tasks",
        params=params,
    )

    assert response.status_code == 422
    assert service.list_calls == []


def test_list_tasks_requires_authentication() -> None:
    app = create_app()
    service = FakeTaskService()
    app.dependency_overrides[get_task_service] = lambda: service
    client = TestClient(app)

    response = client.get(f"/api/v1/projects/{uuid4()}/tasks")

    assert response.status_code == 401
    assert service.list_calls == []


def test_list_tasks_returns_not_found_for_inaccessible_project() -> None:
    service = FakeTaskService()
    project_id = uuid4()
    service.error = EntityNotFoundError("Project", project_id)
    client = create_authenticated_client(make_user(), service)

    response = client.get(f"/api/v1/projects/{project_id}/tasks")

    assert response.status_code == 404
    assert response.json()["error"]["details"] == {
        "entity": "Project",
        "id": str(project_id),
    }


def test_list_tasks_forwards_filters() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()
    assignee_id = uuid4()
    creator_id = uuid4()

    response = client.get(
        f"/api/v1/projects/{project_id}/tasks",
        params={
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "assignee_id": str(assignee_id),
            "created_by": str(creator_id),
            "due_from": "2026-08-01T00:00:00Z",
            "due_to": "2026-08-31T23:59:00Z",
        },
    )

    assert response.status_code == 200
    assert service.list_calls == [
        (
            project_id,
            current_user,
            1,
            20,
            TaskFilters(
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH,
                assignee_id=assignee_id,
                created_by=creator_id,
                due_from=datetime(2026, 8, 1, tzinfo=UTC),
                due_to=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
            ),
        )
    ]


def test_list_tasks_forwards_unassigned_filter() -> None:
    current_user = make_user()
    service = FakeTaskService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()

    response = client.get(
        f"/api/v1/projects/{project_id}/tasks",
        params={"unassigned": "true"},
    )

    assert response.status_code == 200
    assert service.list_calls == [
        (
            project_id,
            current_user,
            1,
            20,
            TaskFilters(unassigned=True),
        )
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"status": "INVALID"},
        {"priority": "INVALID"},
        {"assignee_id": "not-a-uuid"},
        {"created_by": "not-a-uuid"},
        {"due_from": "2026-08-01T00:00:00"},
        {"due_to": "2026-08-31T23:59:00"},
        {
            "assignee_id": str(uuid4()),
            "unassigned": "true",
        },
        {
            "due_from": "2026-09-01T00:00:00Z",
            "due_to": "2026-08-01T00:00:00Z",
        },
    ],
)
def test_list_tasks_rejects_invalid_filters(
    params: dict[str, object],
) -> None:
    service = FakeTaskService()
    client = create_authenticated_client(make_user(), service)

    response = client.get(
        f"/api/v1/projects/{uuid4()}/tasks",
        params=params,
    )

    assert response.status_code == 422
    assert service.list_calls == []
