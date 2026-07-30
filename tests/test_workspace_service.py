from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.enums import UserRole
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceCreateData
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace_service import WorkspaceService


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.create_calls: list[WorkspaceCreateData] = []

    async def create(
        self,
        obj_in: WorkspaceCreateData,
        *,
        refresh: bool = True,
    ) -> Workspace:
        self.create_calls.append(obj_in)
        now = datetime.now(UTC)
        return Workspace(
            id=uuid4(),
            name=obj_in.name,
            owner_id=obj_in.owner_id,
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


@pytest.mark.asyncio
async def test_create_workspace_assigns_authenticated_user_as_owner() -> None:
    repo = FakeWorkspaceRepository()
    service = WorkspaceService(repo)  # type: ignore[arg-type]
    current_user = make_user()

    workspace = await service.create_workspace(
        current_user,
        WorkspaceCreate(name="Engineering"),
    )

    assert workspace.name == "Engineering"
    assert workspace.owner_id == current_user.id
    assert repo.create_calls == [
        WorkspaceCreateData(
            name="Engineering",
            owner_id=current_user.id,
        )
    ]
