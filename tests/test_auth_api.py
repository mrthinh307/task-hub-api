from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service
from app.core.config import settings
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.main import create_app
from app.models.user import User
from app.services.auth_service import AuthResult, TokenPair


class FakeAuthService:
    def __init__(self):
        self.user = User(
            id=uuid4(),
            email="user@example.com",
            full_name="Example User",
            hashed_password="not-used-by-api-tests",
        )
        self.tokens = TokenPair(
            access_token="access.jwt.value",
            refresh_token="refresh.jwt.value",
        )
        self.refreshed_with = None
        self.logged_out_with = None

    async def register(self, payload):
        if str(payload.email) == "existing@example.com":
            raise EmailAlreadyRegisteredError
        return AuthResult(user=self.user, tokens=self.tokens)

    async def login(self, payload):
        if payload.password == "wrong-password":
            raise InvalidCredentialsError
        return AuthResult(user=self.user, tokens=self.tokens)

    async def refresh(self, refresh_token):
        self.refreshed_with = refresh_token
        return self.tokens

    async def logout(self, refresh_token):
        self.logged_out_with = refresh_token


def create_client(fake_service: FakeAuthService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: fake_service
    return TestClient(app)


def test_register_returns_user_and_secure_http_only_cookies(monkeypatch) -> None:
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    fake_service = FakeAuthService()
    client = create_client(fake_service)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "password123",
            "full_name": "Example User",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(fake_service.user.id),
        "email": "user@example.com",
        "full_name": "Example User",
    }
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 2
    assert all("HttpOnly" in header for header in set_cookie_headers)
    assert all("Secure" in header for header in set_cookie_headers)
    assert all("SameSite=lax" in header for header in set_cookie_headers)
    assert any("Path=/api/v1" in header for header in set_cookie_headers)
    assert any("Path=/api/v1/auth" in header for header in set_cookie_headers)
    assert "access.jwt.value" not in response.text
    assert "refresh.jwt.value" not in response.text


def test_register_duplicate_email_uses_standard_error_response() -> None:
    client = create_client(FakeAuthService())

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "existing@example.com",
            "password": "password123",
            "full_name": "Example User",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": 409,
            "message": "Email is already registered",
            "details": None,
        }
    }


def test_login_uses_generic_unauthorized_error() -> None:
    client = create_client(FakeAuthService())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": 401,
            "message": "Invalid email or password",
            "details": None,
        }
    }


def test_request_validation_uses_standard_error_response() -> None:
    client = create_client(FakeAuthService())

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "short",
            "full_name": "Example User",
        },
    )

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == 422
    assert body["error"]["message"] == "Request validation failed"
    assert {detail["field"] for detail in body["error"]["details"]} == {
        "body.email",
        "body.password",
    }
    assert all(
        set(detail) == {"field", "message", "type"}
        for detail in body["error"]["details"]
    )


def test_refresh_reads_cookie_and_rotates_both_cookies() -> None:
    fake_service = FakeAuthService()
    client = create_client(fake_service)
    client.cookies.set(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        "old-refresh-token",
        path="/api/v1/auth",
    )

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 204
    assert fake_service.refreshed_with == "old-refresh-token"
    assert len(response.headers.get_list("set-cookie")) == 2


def test_refresh_without_cookie_returns_401_and_clears_cookies() -> None:
    client = create_client(FakeAuthService())

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": 401,
            "message": "Invalid or expired authentication token",
            "details": None,
        }
    }
    assert len(response.headers.get_list("set-cookie")) == 2


def test_unknown_route_uses_standard_error_response() -> None:
    client = create_client(FakeAuthService())

    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": 404,
            "message": "Not Found",
            "details": None,
        }
    }


def test_logout_revokes_cookie_session_and_clears_cookies() -> None:
    fake_service = FakeAuthService()
    client = create_client(fake_service)
    client.cookies.set(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        "refresh-token",
        path="/api/v1/auth",
    )

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert fake_service.logged_out_with == "refresh-token"
    assert len(response.headers.get_list("set-cookie")) == 2


def test_openapi_contains_auth_user_and_health_operations() -> None:
    client = create_client(FakeAuthService())

    openapi = client.get("/api/v1/openapi.json").json()
    paths = set(openapi["paths"])

    assert paths == {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/users/me",
        "/api/v1/workspaces",
        "/health",
    }
    assert (
        openapi["paths"]["/api/v1/auth/register"]["post"]["responses"]["409"][
            "content"
        ]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )
    assert set(openapi["components"]["schemas"]["ErrorContent"]["properties"]) == {
        "code",
        "message",
        "details",
    }
    assert (
        openapi["components"]["schemas"]["ErrorContent"]["properties"]["code"]["type"]
        == "integer"
    )
    user_me_operations = openapi["paths"]["/api/v1/users/me"]
    assert set(user_me_operations) == {"get", "patch"}
    assert set(user_me_operations["patch"]["responses"]) == {
        "200",
        "401",
        "403",
        "409",
        "422",
    }
