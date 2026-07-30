from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_task_service
from app.core.enums import TaskPriority, TaskStatus, UserRole
from app.core.exceptions import (
    ArchivedProjectError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.main import create_app
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate


class FakeTaskService:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, User, TaskCreate]] = []
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
