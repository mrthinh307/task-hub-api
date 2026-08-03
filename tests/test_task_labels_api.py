from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_task_label_service
from app.core.enums import UserRole
from app.core.exceptions import TaskLabelProjectMismatchError
from app.main import create_app
from app.models.user import User


class FakeTaskLabelService:
    def __init__(self) -> None:
        self.assign_calls: list[tuple[UUID, UUID, User]] = []
        self.remove_calls: list[tuple[UUID, UUID, User]] = []
        self.error: Exception | None = None

    async def assign_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user: User,
    ) -> None:
        self.assign_calls.append((task_id, label_id, current_user))
        if self.error is not None:
            raise self.error

    async def remove_label(
        self,
        task_id: UUID,
        label_id: UUID,
        current_user: User,
    ) -> None:
        self.remove_calls.append((task_id, label_id, current_user))
        if self.error is not None:
            raise self.error


def make_user() -> User:
    return User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Task Label Editor",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeTaskLabelService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_task_label_service] = lambda: service
    return TestClient(app)


def test_assign_label_to_task_returns_no_content() -> None:
    current_user = make_user()
    service = FakeTaskLabelService()
    client = create_authenticated_client(current_user, service)
    task_id = uuid4()
    label_id = uuid4()

    response = client.put(f"/api/v1/tasks/{task_id}/labels/{label_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.assign_calls == [(task_id, label_id, current_user)]


def test_remove_label_from_task_returns_no_content() -> None:
    current_user = make_user()
    service = FakeTaskLabelService()
    client = create_authenticated_client(current_user, service)
    task_id = uuid4()
    label_id = uuid4()

    response = client.delete(f"/api/v1/tasks/{task_id}/labels/{label_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.remove_calls == [(task_id, label_id, current_user)]


@pytest.mark.parametrize("method", ["put", "delete"])
def test_task_label_endpoints_require_authentication(method: str) -> None:
    app = create_app()
    service = FakeTaskLabelService()
    app.dependency_overrides[get_task_label_service] = lambda: service
    client = TestClient(app)

    response = client.request(
        method,
        f"/api/v1/tasks/{uuid4()}/labels/{uuid4()}",
    )

    assert response.status_code == 401
    assert service.assign_calls == []
    assert service.remove_calls == []


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/tasks/not-a-uuid/labels/{uuid4()}",
        f"/api/v1/tasks/{uuid4()}/labels/not-a-uuid",
    ],
)
def test_assign_label_rejects_invalid_ids(path: str) -> None:
    service = FakeTaskLabelService()
    client = create_authenticated_client(make_user(), service)

    response = client.put(path)

    assert response.status_code == 422
    assert service.assign_calls == []


def test_assign_label_maps_cross_project_conflict() -> None:
    service = FakeTaskLabelService()
    task_id = uuid4()
    label_id = uuid4()
    task_project_id = uuid4()
    label_project_id = uuid4()
    service.error = TaskLabelProjectMismatchError(
        task_id,
        label_id,
        task_project_id,
        label_project_id,
    )
    client = create_authenticated_client(make_user(), service)

    response = client.put(f"/api/v1/tasks/{task_id}/labels/{label_id}")

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {
        "task_id": str(task_id),
        "label_id": str(label_id),
        "task_project_id": str(task_project_id),
        "label_project_id": str(label_project_id),
    }
