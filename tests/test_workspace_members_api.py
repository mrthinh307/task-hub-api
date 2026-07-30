from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_workspace_membership_service,
)
from app.core.enums import UserRole, WorkspaceMemberRole
from app.core.exceptions import (
    WorkspaceMemberAlreadyExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceOwnerRemovalError,
)
from app.main import create_app
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUserResponse,
)


class FakeWorkspaceMembershipService:
    def __init__(self, member_user: User) -> None:
        self.member_user = member_user
        self.calls: list[tuple[UUID, User, WorkspaceMemberCreate]] = []
        self.error: Exception | None = None
        self.remove_calls: list[tuple[UUID, UUID, User]] = []
        self.remove_error: Exception | None = None

    async def add_member(
        self,
        workspace_id: UUID,
        current_user: User,
        payload: WorkspaceMemberCreate,
    ) -> WorkspaceMemberResponse:
        self.calls.append((workspace_id, current_user, payload))
        if self.error is not None:
            raise self.error

        now = datetime.now(UTC)
        return WorkspaceMemberResponse(
            id=uuid4(),
            workspace_id=workspace_id,
            user=WorkspaceMemberUserResponse.model_validate(self.member_user),
            role=payload.role,
            created_at=now,
            updated_at=now,
        )

    async def remove_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        current_user: User,
    ) -> None:
        self.remove_calls.append((workspace_id, user_id, current_user))
        if self.remove_error is not None:
            raise self.remove_error


def make_user(email: str) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Example User",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeWorkspaceMembershipService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_workspace_membership_service] = lambda: service
    return TestClient(app)


def test_add_workspace_member_returns_created_membership() -> None:
    owner = make_user("owner@example.com")
    member_user = make_user("member@example.com")
    service = FakeWorkspaceMembershipService(member_user)
    client = create_authenticated_client(owner, service)
    workspace_id = uuid4()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "member@example.com", "role": "EDITOR"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "workspace_id": str(workspace_id),
        "user": {
            "id": str(member_user.id),
            "email": member_user.email,
            "full_name": member_user.full_name,
        },
        "role": "EDITOR",
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }
    assert service.calls == [
        (
            workspace_id,
            owner,
            WorkspaceMemberCreate(
                email="member@example.com",
                role=WorkspaceMemberRole.EDITOR,
            ),
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "role": "EDITOR"},
        {"email": "member@example.com", "role": "OWNER"},
        {"email": "member@example.com", "role": "ADMIN"},
        {"email": "member@example.com", "role": "VIEWER", "extra": True},
    ],
)
def test_add_workspace_member_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    client = create_authenticated_client(owner, service)

    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/members",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Request validation failed"
    assert service.calls == []


def test_add_workspace_member_maps_duplicate_to_conflict() -> None:
    owner = make_user("owner@example.com")
    member_user = make_user("member@example.com")
    service = FakeWorkspaceMembershipService(member_user)
    workspace_id = uuid4()
    service.error = WorkspaceMemberAlreadyExistsError(
        workspace_id,
        member_user.id,
    )
    client = create_authenticated_client(owner, service)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": member_user.email, "role": "VIEWER"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": 409,
        "message": "User is already a member of this workspace",
        "details": {
            "workspace_id": str(workspace_id),
            "user_id": str(member_user.id),
        },
    }


def test_add_workspace_member_requires_authentication() -> None:
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    app = create_app()
    app.dependency_overrides[get_workspace_membership_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/workspaces/{uuid4()}/members",
        json={"email": "member@example.com", "role": "VIEWER"},
    )

    assert response.status_code == 401
    assert service.calls == []


def test_add_workspace_member_documents_expected_responses() -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    client = create_authenticated_client(owner, service)

    operation = client.get("/api/v1/openapi.json").json()["paths"][
        "/api/v1/workspaces/{workspace_id}/members"
    ]["post"]

    assert set(operation["responses"]) == {
        "201",
        "401",
        "403",
        "404",
        "409",
        "422",
    }


def test_remove_workspace_member_returns_no_content() -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    client = create_authenticated_client(owner, service)
    workspace_id = uuid4()
    user_id = uuid4()

    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{user_id}"
    )

    assert response.status_code == 204
    assert response.content == b""
    assert service.remove_calls == [(workspace_id, user_id, owner)]


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/workspaces/not-a-uuid/members/{uuid4()}",
        f"/api/v1/workspaces/{uuid4()}/members/not-a-uuid",
    ],
)
def test_remove_workspace_member_rejects_invalid_ids(path: str) -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    client = create_authenticated_client(owner, service)

    response = client.delete(path)

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Request validation failed"
    assert service.remove_calls == []


def test_remove_workspace_member_maps_missing_member_to_not_found() -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    workspace_id = uuid4()
    user_id = uuid4()
    service.remove_error = WorkspaceMemberNotFoundError(workspace_id, user_id)
    client = create_authenticated_client(owner, service)

    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{user_id}"
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": 404,
        "message": "Workspace member not found",
        "details": {
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
        },
    }


def test_remove_workspace_member_rejects_owner_removal() -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    workspace_id = uuid4()
    service.remove_error = WorkspaceOwnerRemovalError(workspace_id, owner.id)
    client = create_authenticated_client(owner, service)

    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner.id}"
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "Workspace owner cannot be removed through the member endpoint"
    )


def test_remove_workspace_member_requires_authentication() -> None:
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    app = create_app()
    app.dependency_overrides[get_workspace_membership_service] = lambda: service
    client = TestClient(app)

    response = client.delete(
        f"/api/v1/workspaces/{uuid4()}/members/{uuid4()}"
    )

    assert response.status_code == 401
    assert service.remove_calls == []


def test_remove_workspace_member_documents_expected_responses() -> None:
    owner = make_user("owner@example.com")
    service = FakeWorkspaceMembershipService(make_user("member@example.com"))
    client = create_authenticated_client(owner, service)

    operation = client.get("/api/v1/openapi.json").json()["paths"][
        "/api/v1/workspaces/{workspace_id}/members/{user_id}"
    ]["delete"]

    assert set(operation["responses"]) == {
        "204",
        "401",
        "403",
        "404",
        "409",
        "422",
    }
