from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_project_service
from app.core.enums import ProjectStatus, UserRole
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.main import create_app
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate


class FakeProjectService:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, User, ProjectCreate]] = []
        self.error: Exception | None = None

    async def create_project(
        self,
        workspace_id: UUID,
        current_user: User,
        payload: ProjectCreate,
    ) -> Project:
        self.calls.append((workspace_id, current_user, payload))
        if self.error is not None:
            raise self.error

        now = datetime.now(UTC)
        return Project(
            id=uuid4(),
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
            status=ProjectStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )


def make_user() -> User:
    return User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Project Editor",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeProjectService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_project_service] = lambda: service
    return TestClient(app)


def test_create_project_returns_created_project() -> None:
    current_user = make_user()
    service = FakeProjectService()
    client = create_authenticated_client(current_user, service)
    workspace_id = uuid4()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={
            "name": "  Task Hub  ",
            "description": "Backend API",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "workspace_id": str(workspace_id),
        "name": "Task Hub",
        "description": "Backend API",
        "status": "ACTIVE",
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }
    assert service.calls == [
        (
            workspace_id,
            current_user,
            ProjectCreate(name="Task Hub", description="Backend API"),
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "   "},
        {"name": "x" * 256},
        {"name": "Task Hub", "status": "ARCHIVED"},
        {"name": "Task Hub", "workspace_id": str(uuid4())},
        {"name": "Task Hub", "extra": True},
    ],
)
def test_create_project_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    service = FakeProjectService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/projects",
        json=payload,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_create_project_rejects_invalid_workspace_id() -> None:
    service = FakeProjectService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        "/api/v1/workspaces/not-a-uuid/projects",
        json={"name": "Task Hub"},
    )

    assert response.status_code == 422
    assert service.calls == []


def test_create_project_requires_authentication() -> None:
    app = create_app()
    service = FakeProjectService()
    app.dependency_overrides[get_project_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/projects",
        json={"name": "Task Hub"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == (
        "Invalid or expired authentication token"
    )
    assert service.calls == []


def test_create_project_returns_forbidden_for_viewer() -> None:
    service = FakeProjectService()
    workspace_id = uuid4()
    service.error = PermissionDeniedError(
        message="Viewer role cannot create projects in this workspace",
        details={"workspace_id": str(workspace_id)},
    )
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "Task Hub"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": 403,
        "message": "Viewer role cannot create projects in this workspace",
        "details": {"workspace_id": str(workspace_id)},
    }


def test_create_project_returns_not_found_for_inaccessible_workspace() -> None:
    service = FakeProjectService()
    workspace_id = uuid4()
    service.error = EntityNotFoundError("Workspace", workspace_id)
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "Task Hub"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": 404,
        "message": f"Workspace with id {workspace_id} not found",
        "details": {
            "entity": "Workspace",
            "id": str(workspace_id),
        },
    }
