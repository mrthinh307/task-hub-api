from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_repository
from app.core.config import settings
from app.core.enums import TokenType, UserRole
from app.core.security import create_token, get_password_hash, verify_password
from app.main import create_app
from app.models.user import User
from app.repositories.user_repository import UserUpdateData


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.update_calls: list[dict[str, str | None]] = []

    async def get_by_id(self, entity_id: UUID) -> User | None:
        if self.user is not None and self.user.id == entity_id:
            return self.user
        return None

    async def update(
        self,
        db_obj: User,
        obj_in: UserUpdateData,
        *,
        refresh: bool = True,
    ) -> User:
        update_data = obj_in.model_dump(exclude_unset=True)
        self.update_calls.append(update_data)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        return db_obj


def make_user(*, is_active: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="user@example.com",
        full_name="Example User",
        hashed_password=get_password_hash("password123"),
        role=UserRole.MEMBER,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def create_client(
    user: User | None,
) -> tuple[TestClient, FakeUserRepository]:
    repo = FakeUserRepository(user)
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repo
    return TestClient(app), repo


def set_access_cookie(
    client: TestClient,
    user_id: UUID,
    *,
    token_type: TokenType = TokenType.ACCESS,
    expires_delta: timedelta = timedelta(minutes=5),
) -> None:
    token, _, _ = create_token(user_id, token_type, expires_delta)
    client.cookies.set(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        token,
        path=settings.API_V1_STR,
    )


def test_get_profile_returns_authenticated_user() -> None:
    user = make_user()
    client, _ = create_client(user)
    set_access_cookie(client, user.id)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": user.updated_at.isoformat().replace("+00:00", "Z"),
    }
    assert "hashed_password" not in response.text


@pytest.mark.parametrize("include_bearer_header", [False, True])
def test_get_profile_requires_access_cookie_and_ignores_bearer_header(
    include_bearer_header: bool,
) -> None:
    user = make_user()
    client, _ = create_client(user)
    token, _, _ = create_token(user.id, TokenType.ACCESS, timedelta(minutes=5))
    headers = {"Authorization": f"Bearer {token}"} if include_bearer_header else {}

    response = client.get(
        "/api/v1/users/me",
        headers=headers,
    )

    assert response.status_code == 401
    assert len(response.headers.get_list("set-cookie")) == 2


@pytest.mark.parametrize("token_value", ["not-a-jwt", None])
def test_get_profile_rejects_invalid_or_expired_token(
    token_value: str | None,
) -> None:
    user = make_user()
    client, _ = create_client(user)
    if token_value is None:
        token_value, _, _ = create_token(
            user.id,
            TokenType.ACCESS,
            timedelta(seconds=-1),
        )
    client.cookies.set(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        token_value,
        path=settings.API_V1_STR,
    )

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert len(response.headers.get_list("set-cookie")) == 2


def test_get_profile_rejects_refresh_token_in_access_cookie() -> None:
    user = make_user()
    client, _ = create_client(user)
    set_access_cookie(client, user.id, token_type=TokenType.REFRESH)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_get_profile_rejects_missing_user() -> None:
    client, _ = create_client(None)
    set_access_cookie(client, uuid4())

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_get_profile_rejects_inactive_user_and_clears_cookies() -> None:
    user = make_user(is_active=False)
    client, _ = create_client(user)
    set_access_cookie(client, user.id)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 403
    assert len(response.headers.get_list("set-cookie")) == 2


def test_patch_profile_updates_full_name() -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)
    old_hash = user.hashed_password

    response = client.patch(
        "/api/v1/users/me",
        json={"full_name": "  Updated User  "},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated User"
    assert user.hashed_password == old_hash
    assert repo.update_calls == [{"full_name": "Updated User"}]


def test_patch_profile_updates_only_password() -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)

    response = client.patch(
        "/api/v1/users/me",
        json={
            "current_password": "password123",
            "new_password": "new-password-456",
        },
    )

    assert response.status_code == 200
    assert user.full_name == "Example User"
    assert verify_password("new-password-456", user.hashed_password)
    assert set(repo.update_calls[0]) == {"hashed_password"}


def test_patch_profile_updates_name_and_password_without_rotating_cookies() -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)

    response = client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Updated User",
            "current_password": "password123",
            "new_password": "new-password-456",
        },
    )

    assert response.status_code == 200
    assert user.full_name == "Updated User"
    assert verify_password("new-password-456", user.hashed_password)
    assert set(repo.update_calls[0]) == {"full_name", "hashed_password"}
    assert response.headers.get_list("set-cookie") == []


def test_patch_profile_rejects_wrong_current_password_without_partial_update() -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)

    response = client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Must Not Change",
            "current_password": "wrong-password",
            "new_password": "new-password-456",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Current password is incorrect"
    assert response.headers.get_list("set-cookie") == []
    assert user.full_name == "Example User"
    assert repo.update_calls == []


def test_patch_profile_rejects_current_password_as_new_password() -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)

    response = client.patch(
        "/api/v1/users/me",
        json={
            "current_password": "password123",
            "new_password": "password123",
        },
    )

    assert response.status_code == 409
    assert repo.update_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"full_name": None},
        {"full_name": "   "},
        {"full_name": "x" * 256},
        {"email": "new@example.com"},
        {"current_password": None, "new_password": "new-password-456"},
        {"current_password": "password123", "new_password": None},
        {"current_password": "password123"},
        {"new_password": "new-password-456"},
        {"current_password": "password123", "new_password": "short"},
        {"current_password": "password123", "new_password": "x" * 73},
    ],
)
def test_patch_profile_rejects_invalid_payload(payload: dict[str, object]) -> None:
    user = make_user()
    client, repo = create_client(user)
    set_access_cookie(client, user.id)

    response = client.patch("/api/v1/users/me", json=payload)

    assert response.status_code == 422
    assert repo.update_calls == []
