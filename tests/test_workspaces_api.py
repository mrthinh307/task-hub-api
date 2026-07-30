from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_workspace_service
from app.core.enums import UserRole
from app.main import create_app
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.create_calls: list[tuple[User, WorkspaceCreate]] = []

    async def create_workspace(
        self,
        current_user: User,
        payload: WorkspaceCreate,
    ) -> Workspace:
        self.create_calls.append((current_user, payload))
        now = datetime.now(UTC)
        return Workspace(
            id=uuid4(),
            name=payload.name,
            owner_id=current_user.id,
            created_at=now,
            updated_at=now,
        )


def make_user() -> User:
    return User(
        id=uuid4(),
        email="owner@example.com",
        full_name="Workspace Owner",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeWorkspaceService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_workspace_service] = lambda: service
    return TestClient(app)


def test_create_workspace_returns_created_workspace() -> None:
    current_user = make_user()
    service = FakeWorkspaceService()
    client = create_authenticated_client(current_user, service)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "  Engineering  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "name": "Engineering",
        "owner_id": str(current_user.id),
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }
    assert service.create_calls[0][0] is current_user
    assert service.create_calls[0][1].name == "Engineering"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 256},
        {"name": "Engineering", "owner_id": str(uuid4())},
    ],
)
def test_create_workspace_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    service = FakeWorkspaceService()
    client = create_authenticated_client(make_user(), service)

    response = client.post("/api/v1/workspaces", json=payload)

    assert response.status_code == 422
    assert service.create_calls == []


def test_create_workspace_requires_authentication() -> None:
    app = create_app()
    app.dependency_overrides[get_workspace_service] = lambda: FakeWorkspaceService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Engineering"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == (
        "Invalid or expired authentication token"
    )


def test_openapi_documents_create_workspace_responses() -> None:
    client = TestClient(create_app())

    operation = client.get("/api/v1/openapi.json").json()["paths"][
        "/api/v1/workspaces"
    ]["post"]

    assert set(operation["responses"]) == {"201", "401", "403", "422"}
    assert (
        operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/WorkspaceResponse"
    )
