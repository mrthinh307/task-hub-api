from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.enums import ProjectStatus, UserRole, WorkspaceAccessRole
from app.core.exceptions import (
    ArchivedLabelMutationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.models.label import Label
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.label_repository import LabelCreateData, LabelUpdateData
from app.repositories.workspace_repository import WorkspaceAccess
from app.schemas.label import LabelCreate, LabelUpdate
from app.services.label_service import LabelService


class FakeDatabaseError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate
        super().__init__(sqlstate)


class FakeLabelRepository:
    def __init__(self) -> None:
        self.labels: dict[UUID, Label] = {}
        self.create_calls: list[LabelCreateData] = []
        self.update_calls: list[tuple[Label, LabelUpdateData]] = []
        self.delete_calls: list[UUID] = []
        self.list_calls: list[UUID] = []
        self.name_lookup_calls: list[tuple[UUID, str]] = []
        self.create_error: IntegrityError | None = None
        self.update_error: IntegrityError | None = None

    async def get_by_id(self, label_id: UUID) -> Label | None:
        return self.labels.get(label_id)

    async def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str,
    ) -> Label | None:
        self.name_lookup_calls.append((project_id, name))
        return next(
            (
                label
                for label in self.labels.values()
                if label.project_id == project_id and label.name == name
            ),
            None,
        )

    async def create(
        self,
        obj_in: LabelCreateData,
        *,
        refresh: bool = True,
    ) -> Label:
        self.create_calls.append(obj_in)
        if self.create_error is not None:
            raise self.create_error
        now = datetime.now(UTC)
        label = Label(
            id=uuid4(),
            project_id=obj_in.project_id,
            name=obj_in.name,
            color=obj_in.color,
            created_at=now,
            updated_at=now,
        )
        self.labels[label.id] = label
        return label

    async def list_by_project(self, project_id: UUID) -> Sequence[Label]:
        self.list_calls.append(project_id)
        return [
            label for label in self.labels.values() if label.project_id == project_id
        ]

    async def update(
        self,
        label: Label,
        obj_in: LabelUpdateData,
        *,
        refresh: bool = True,
    ) -> Label:
        self.update_calls.append((label, obj_in))
        if self.update_error is not None:
            raise self.update_error
        for field, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(label, field, value)
        return label

    async def delete(self, label_id: UUID) -> bool:
        self.delete_calls.append(label_id)
        return self.labels.pop(label_id, None) is not None


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.access: WorkspaceAccess | None = None
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_accessible_by_id(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceAccess | None:
        self.calls.append((workspace_id, user_id))
        return self.access


def make_user() -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        full_name="Label User",
        hashed_password="not-used",
        role=UserRole.MEMBER,
        is_active=True,
    )


def make_service(
    *,
    role: WorkspaceAccessRole = WorkspaceAccessRole.EDITOR,
    project_status: ProjectStatus = ProjectStatus.ACTIVE,
) -> tuple[
    LabelService,
    FakeLabelRepository,
    FakeProjectRepository,
    FakeWorkspaceRepository,
    Project,
    User,
]:
    current_user = make_user()
    workspace = Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=uuid4(),
    )
    project = Project(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Task Hub",
        description=None,
        status=project_status,
    )
    label_repo = FakeLabelRepository()
    project_repo = FakeProjectRepository()
    project_repo.projects[project.id] = project
    workspace_repo = FakeWorkspaceRepository()
    workspace_repo.access = WorkspaceAccess(workspace=workspace, role=role)
    service = LabelService(
        label_repo,  # type: ignore[arg-type]
        project_repo,  # type: ignore[arg-type]
        workspace_repo,  # type: ignore[arg-type]
    )
    return (
        service,
        label_repo,
        project_repo,
        workspace_repo,
        project,
        current_user,
    )


@pytest.mark.parametrize(
    "role",
    [WorkspaceAccessRole.OWNER, WorkspaceAccessRole.EDITOR],
)
@pytest.mark.asyncio
async def test_create_label_allows_project_writers(
    role: WorkspaceAccessRole,
) -> None:
    service, repo, _, _, project, current_user = make_service(role=role)

    label = await service.create_label(
        project.id,
        current_user,
        LabelCreate(name="backend", color="#2563EB"),
    )

    assert label.project_id == project.id
    assert repo.create_calls == [
        LabelCreateData(
            project_id=project.id,
            name="backend",
            color="#2563EB",
        )
    ]


@pytest.mark.asyncio
async def test_list_and_get_labels_allow_viewer() -> None:
    service, repo, _, _, project, current_user = make_service(
        role=WorkspaceAccessRole.VIEWER,
        project_status=ProjectStatus.ARCHIVED,
    )
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[label.id] = label

    labels = await service.list_labels(project.id, current_user)
    loaded = await service.get_label(label.id, current_user)

    assert list(labels) == [label]
    assert loaded is label


@pytest.mark.asyncio
async def test_update_and_delete_label() -> None:
    service, repo, _, _, project, current_user = make_service()
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[label.id] = label

    updated = await service.update_label(
        label.id,
        current_user,
        LabelUpdate(name="api", color="#16A34A"),
    )
    await service.delete_label(label.id, current_user)

    assert updated.name == "api"
    assert updated.color == "#16A34A"
    assert repo.update_calls == [
        (
            label,
            LabelUpdateData(name="api", color="#16A34A"),
        )
    ]
    assert repo.delete_calls == [label.id]


@pytest.mark.asyncio
async def test_create_label_rejects_duplicate_name() -> None:
    service, repo, _, _, project, current_user = make_service()
    existing = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[existing.id] = existing

    with pytest.raises(EntityAlreadyExistsError):
        await service.create_label(
            project.id,
            current_user,
            LabelCreate(name="backend"),
        )

    assert repo.create_calls == []


@pytest.mark.asyncio
async def test_create_label_maps_unique_race_to_conflict() -> None:
    service, repo, _, _, project, current_user = make_service()
    repo.create_error = IntegrityError(
        statement=None,
        params=None,
        orig=FakeDatabaseError("23505"),
    )

    with pytest.raises(EntityAlreadyExistsError):
        await service.create_label(
            project.id,
            current_user,
            LabelCreate(name="backend"),
        )


@pytest.mark.asyncio
async def test_update_label_rejects_duplicate_name() -> None:
    service, repo, _, _, project, current_user = make_service()
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    other = Label(
        id=uuid4(),
        project_id=project.id,
        name="api",
        color="#16A34A",
    )
    repo.labels[label.id] = label
    repo.labels[other.id] = other

    with pytest.raises(EntityAlreadyExistsError):
        await service.update_label(
            label.id,
            current_user,
            LabelUpdate(name="api"),
        )

    assert repo.update_calls == []


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.asyncio
async def test_label_mutations_reject_viewer(operation: str) -> None:
    service, repo, _, _, project, current_user = make_service(
        role=WorkspaceAccessRole.VIEWER
    )
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[label.id] = label

    with pytest.raises(PermissionDeniedError):
        if operation == "create":
            await service.create_label(
                project.id,
                current_user,
                LabelCreate(name="api"),
            )
        elif operation == "update":
            await service.update_label(
                label.id,
                current_user,
                LabelUpdate(name="api"),
            )
        else:
            await service.delete_label(label.id, current_user)


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.asyncio
async def test_label_mutations_reject_archived_project(operation: str) -> None:
    service, repo, _, _, project, current_user = make_service(
        project_status=ProjectStatus.ARCHIVED
    )
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[label.id] = label

    with pytest.raises(ArchivedLabelMutationError):
        if operation == "create":
            await service.create_label(
                project.id,
                current_user,
                LabelCreate(name="api"),
            )
        elif operation == "update":
            await service.update_label(
                label.id,
                current_user,
                LabelUpdate(name="api"),
            )
        else:
            await service.delete_label(label.id, current_user)


@pytest.mark.asyncio
async def test_get_label_hides_inaccessible_project() -> None:
    service, repo, _, workspace_repo, project, current_user = make_service()
    label = Label(
        id=uuid4(),
        project_id=project.id,
        name="backend",
        color="#2563EB",
    )
    repo.labels[label.id] = label
    workspace_repo.access = None

    with pytest.raises(EntityNotFoundError) as exc_info:
        await service.get_label(label.id, current_user)

    assert exc_info.value.details == {
        "entity": "Label",
        "id": str(label.id),
    }
