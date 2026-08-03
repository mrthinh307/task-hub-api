from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_comment_service, get_current_user
from app.core.enums import UserRole
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.main import create_app
from app.models.comment import Comment
from app.models.user import User
from app.schemas.comment import CommentCreate


class FakeCommentService:
    def __init__(self) -> None:
        self.add_calls: list[tuple[UUID, User, CommentCreate]] = []
        self.delete_calls: list[tuple[UUID, User]] = []
        self.error: Exception | None = None

    async def add_comment(
        self,
        task_id: UUID,
        current_user: User,
        payload: CommentCreate,
    ) -> Comment:
        self.add_calls.append((task_id, current_user, payload))
        self._raise_error()
        now = datetime.now(UTC)
        return Comment(
            id=uuid4(),
            task_id=task_id,
            author_id=current_user.id,
            content=payload.content,
            created_at=now,
            updated_at=now,
        )

    async def delete_comment(
        self,
        comment_id: UUID,
        current_user: User,
    ) -> None:
        self.delete_calls.append((comment_id, current_user))
        self._raise_error()

    def _raise_error(self) -> None:
        if self.error is not None:
            raise self.error


def make_user() -> User:
    return User(
        id=uuid4(),
        email="commenter@example.com",
        full_name="Task Commenter",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeCommentService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_comment_service] = lambda: service
    return TestClient(app)


def test_add_comment_returns_created_comment() -> None:
    current_user = make_user()
    service = FakeCommentService()
    client = create_authenticated_client(current_user, service)
    task_id = uuid4()

    response = client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "  Ship it  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["task_id"] == str(task_id)
    assert body["author_id"] == str(current_user.id)
    assert body["content"] == "Ship it"
    assert service.add_calls == [
        (task_id, current_user, CommentCreate(content="Ship it"))
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": ""},
        {"content": "   "},
        {"content": None},
        {"content": "x" * 10_001},
        {"content": "Hello", "extra": True},
    ],
)
def test_add_comment_rejects_invalid_payload(
    payload: dict[str, object],
) -> None:
    service = FakeCommentService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/tasks/{uuid4()}/comments",
        json=payload,
    )

    assert response.status_code == 422
    assert service.add_calls == []


def test_delete_comment_returns_no_content() -> None:
    current_user = make_user()
    service = FakeCommentService()
    client = create_authenticated_client(current_user, service)
    comment_id = uuid4()

    response = client.delete(f"/api/v1/comments/{comment_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.delete_calls == [(comment_id, current_user)]


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", f"/api/v1/tasks/{uuid4()}/comments", {"content": "Hello"}),
        ("delete", f"/api/v1/comments/{uuid4()}", None),
    ],
)
def test_comment_endpoints_require_authentication(
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    app = create_app()
    service = FakeCommentService()
    app.dependency_overrides[get_comment_service] = lambda: service
    client = TestClient(app)

    response = client.request(method, path, json=json)

    assert response.status_code == 401
    assert service.add_calls == []
    assert service.delete_calls == []


@pytest.mark.parametrize(
    ("method", "path", "json", "error", "expected_status"),
    [
        (
            "post",
            f"/api/v1/tasks/{uuid4()}/comments",
            {"content": "Hello"},
            EntityNotFoundError("Task", uuid4()),
            404,
        ),
        (
            "delete",
            f"/api/v1/comments/{uuid4()}",
            None,
            EntityNotFoundError("Comment", uuid4()),
            404,
        ),
        (
            "delete",
            f"/api/v1/comments/{uuid4()}",
            None,
            PermissionDeniedError(
                message="Only the comment author can delete this comment"
            ),
            403,
        ),
    ],
)
def test_comment_endpoints_map_domain_errors(
    method: str,
    path: str,
    json: dict[str, object] | None,
    error: Exception,
    expected_status: int,
) -> None:
    service = FakeCommentService()
    service.error = error
    client = create_authenticated_client(make_user(), service)

    response = client.request(method, path, json=json)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", "/api/v1/tasks/not-a-uuid/comments", {"content": "Hello"}),
        ("delete", "/api/v1/comments/not-a-uuid", None),
    ],
)
def test_comment_endpoints_reject_invalid_ids(
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    service = FakeCommentService()
    client = create_authenticated_client(make_user(), service)

    response = client.request(method, path, json=json)

    assert response.status_code == 422
    assert service.add_calls == []
    assert service.delete_calls == []
