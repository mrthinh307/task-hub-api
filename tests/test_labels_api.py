from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_label_service
from app.core.enums import UserRole
from app.core.exceptions import EntityAlreadyExistsError
from app.main import create_app
from app.models.label import Label
from app.models.user import User
from app.schemas.label import LabelCreate, LabelUpdate


class FakeLabelService:
    def __init__(self) -> None:
        self.create_calls: list[tuple[UUID, User, LabelCreate]] = []
        self.list_calls: list[tuple[UUID, User]] = []
        self.get_calls: list[tuple[UUID, User]] = []
        self.update_calls: list[tuple[UUID, User, LabelUpdate]] = []
        self.delete_calls: list[tuple[UUID, User]] = []
        self.labels: dict[UUID, Label] = {}
        self.error: Exception | None = None

    async def create_label(
        self,
        project_id: UUID,
        current_user: User,
        payload: LabelCreate,
    ) -> Label:
        self.create_calls.append((project_id, current_user, payload))
        self._raise_error()
        label = make_label(
            project_id=project_id,
            name=payload.name,
            color=payload.color,
        )
        self.labels[label.id] = label
        return label

    async def list_labels(
        self,
        project_id: UUID,
        current_user: User,
    ) -> Sequence[Label]:
        self.list_calls.append((project_id, current_user))
        self._raise_error()
        return [
            label for label in self.labels.values() if label.project_id == project_id
        ]

    async def get_label(self, label_id: UUID, current_user: User) -> Label:
        self.get_calls.append((label_id, current_user))
        self._raise_error()
        return self.labels[label_id]

    async def update_label(
        self,
        label_id: UUID,
        current_user: User,
        payload: LabelUpdate,
    ) -> Label:
        self.update_calls.append((label_id, current_user, payload))
        self._raise_error()
        label = self.labels[label_id]
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(label, field, value)
        return label

    async def delete_label(self, label_id: UUID, current_user: User) -> None:
        self.delete_calls.append((label_id, current_user))
        self._raise_error()
        self.labels.pop(label_id, None)

    def _raise_error(self) -> None:
        if self.error is not None:
            raise self.error


def make_user() -> User:
    return User(
        id=uuid4(),
        email="editor@example.com",
        full_name="Label Editor",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def make_label(
    *,
    project_id: UUID,
    name: str = "backend",
    color: str = "#2563EB",
) -> Label:
    now = datetime.now(UTC)
    return Label(
        id=uuid4(),
        project_id=project_id,
        name=name,
        color=color,
        created_at=now,
        updated_at=now,
    )


def create_authenticated_client(
    current_user: User,
    service: FakeLabelService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_label_service] = lambda: service
    return TestClient(app)


def test_create_label_returns_created_label() -> None:
    current_user = make_user()
    service = FakeLabelService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()

    response = client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": "  backend  ", "color": "#2563EB"},
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == str(project_id)
    assert response.json()["name"] == "backend"
    assert service.create_calls == [
        (
            project_id,
            current_user,
            LabelCreate(name="backend", color="#2563EB"),
        )
    ]


def test_list_labels_returns_project_labels() -> None:
    current_user = make_user()
    service = FakeLabelService()
    client = create_authenticated_client(current_user, service)
    project_id = uuid4()
    label = make_label(project_id=project_id)
    service.labels[label.id] = label

    response = client.get(f"/api/v1/projects/{project_id}/labels")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(label.id)
    assert service.list_calls == [(project_id, current_user)]


def test_get_label_returns_label() -> None:
    current_user = make_user()
    service = FakeLabelService()
    client = create_authenticated_client(current_user, service)
    label = make_label(project_id=uuid4())
    service.labels[label.id] = label

    response = client.get(f"/api/v1/labels/{label.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(label.id)
    assert service.get_calls == [(label.id, current_user)]


def test_update_label_returns_updated_label() -> None:
    current_user = make_user()
    service = FakeLabelService()
    client = create_authenticated_client(current_user, service)
    label = make_label(project_id=uuid4())
    service.labels[label.id] = label

    response = client.patch(
        f"/api/v1/labels/{label.id}",
        json={"name": "api", "color": "#16A34A"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "api"
    assert response.json()["color"] == "#16A34A"
    assert service.update_calls == [
        (
            label.id,
            current_user,
            LabelUpdate(name="api", color="#16A34A"),
        )
    ]


def test_delete_label_returns_no_content() -> None:
    current_user = make_user()
    service = FakeLabelService()
    client = create_authenticated_client(current_user, service)
    label = make_label(project_id=uuid4())
    service.labels[label.id] = label

    response = client.delete(f"/api/v1/labels/{label.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert service.delete_calls == [(label.id, current_user)]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "backend", "color": "blue"},
        {"name": "backend", "extra": True},
    ],
)
def test_create_label_rejects_invalid_payload(payload: dict[str, object]) -> None:
    service = FakeLabelService()
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/labels",
        json=payload,
    )

    assert response.status_code == 422
    assert service.create_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"color": None},
        {"name": "   "},
        {"color": "#12345"},
        {"extra": True},
    ],
)
def test_update_label_rejects_invalid_payload(payload: dict[str, object]) -> None:
    service = FakeLabelService()
    client = create_authenticated_client(make_user(), service)

    response = client.patch(f"/api/v1/labels/{uuid4()}", json=payload)

    assert response.status_code == 422
    assert service.update_calls == []


def test_create_label_maps_duplicate_name_to_conflict() -> None:
    service = FakeLabelService()
    service.error = EntityAlreadyExistsError("Label", "name", "backend")
    client = create_authenticated_client(make_user(), service)

    response = client.post(
        f"/api/v1/projects/{uuid4()}/labels",
        json={"name": "backend"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {
        "entity": "Label",
        "field": "name",
        "value": "backend",
    }


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", f"/api/v1/projects/{uuid4()}/labels", {"name": "backend"}),
        ("get", f"/api/v1/projects/{uuid4()}/labels", None),
        ("get", f"/api/v1/labels/{uuid4()}", None),
        ("patch", f"/api/v1/labels/{uuid4()}", {"name": "api"}),
        ("delete", f"/api/v1/labels/{uuid4()}", None),
    ],
)
def test_label_endpoints_require_authentication(
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    app = create_app()
    service = FakeLabelService()
    app.dependency_overrides[get_label_service] = lambda: service
    client = TestClient(app)

    response = client.request(method, path, json=json)

    assert response.status_code == 401
