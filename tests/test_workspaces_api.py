from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_workspace_service
from app.core.enums import UserRole, WorkspaceAccessRole
from app.core.exceptions import EntityNotFoundError
from app.main import create_app
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceDetailResponse


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.create_calls: list[tuple[User, WorkspaceCreate]] = []
        self.workspace_details: dict[UUID, WorkspaceDetailResponse] = {}
        self.get_calls: list[tuple[UUID, User]] = []

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

    async def get_workspace(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> WorkspaceDetailResponse:
        self.get_calls.append((workspace_id, current_user))
        detail = self.workspace_details.get(workspace_id)
        if detail is None:
            raise EntityNotFoundError("Workspace", workspace_id)
        return detail


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


@pytest.mark.parametrize(
    "role",
    [
        WorkspaceAccessRole.OWNER,
        WorkspaceAccessRole.EDITOR,
        WorkspaceAccessRole.VIEWER,
    ],
)
def test_get_workspace_returns_accessible_workspace(
    role: WorkspaceAccessRole,
) -> None:
    current_user = make_user()
    service = FakeWorkspaceService()
    client = create_authenticated_client(current_user, service)
    now = datetime.now(UTC)
    workspace_id = uuid4()
    service.workspace_details[workspace_id] = WorkspaceDetailResponse(
        id=workspace_id,
        name="Engineering",
        owner_id=uuid4(),
        role=role,
        created_at=now,
        updated_at=now,
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(workspace_id),
        "name": "Engineering",
        "owner_id": str(service.workspace_details[workspace_id].owner_id),
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "role": role.value,
    }
    assert service.get_calls == [(workspace_id, current_user)]


def test_get_workspace_hides_missing_or_inaccessible_workspace() -> None:
    current_user = make_user()
    service = FakeWorkspaceService()
    client = create_authenticated_client(current_user, service)
    workspace_id = uuid4()

    response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": 404,
        "message": f"Workspace with id {workspace_id} not found",
        "details": {
            "entity": "Workspace",
            "id": str(workspace_id),
        },
    }


def test_get_workspace_rejects_invalid_workspace_id() -> None:
    service = FakeWorkspaceService()
    client = create_authenticated_client(make_user(), service)

    response = client.get("/api/v1/workspaces/not-a-uuid")

    assert response.status_code == 422
    assert service.get_calls == []


def test_get_workspace_requires_authentication() -> None:
    app = create_app()
    app.dependency_overrides[get_workspace_service] = lambda: FakeWorkspaceService()
    client = TestClient(app)

    response = client.get(f"/api/v1/workspaces/{uuid4()}")

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


def test_openapi_documents_get_workspace_responses() -> None:
    client = TestClient(create_app())

    operation = client.get("/api/v1/openapi.json").json()["paths"][
        "/api/v1/workspaces/{workspace_id}"
    ]["get"]

    assert set(operation["responses"]) == {"200", "401", "403", "404", "422"}
    assert (
        operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/WorkspaceDetailResponse"
    )
