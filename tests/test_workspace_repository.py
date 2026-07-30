from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkspaceAccessRole, WorkspaceMemberRole
from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceRepository

type WorkspaceRow = tuple[Workspace, WorkspaceMemberRole | None] | None


def make_workspace(*, owner_id: UUID | None = None) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=owner_id or uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_session(row: WorkspaceRow) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    result = MagicMock()
    tuple_result = MagicMock()
    tuple_result.one_or_none.return_value = row
    result.tuples.return_value = tuple_result
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_get_accessible_workspace_gives_owner_precedence() -> None:
    user_id = uuid4()
    workspace = make_workspace(owner_id=user_id)
    session = make_session((workspace, WorkspaceMemberRole.VIEWER))
    repo = WorkspaceRepository(session)

    access = await repo.get_accessible_by_id(workspace.id, user_id)

    assert access is not None
    assert access.workspace is workspace
    assert access.role is WorkspaceAccessRole.OWNER


@pytest.mark.parametrize(
    ("membership_role", "expected_role"),
    [
        (WorkspaceMemberRole.EDITOR, WorkspaceAccessRole.EDITOR),
        (WorkspaceMemberRole.VIEWER, WorkspaceAccessRole.VIEWER),
    ],
)
@pytest.mark.asyncio
async def test_get_accessible_workspace_maps_member_role(
    membership_role: WorkspaceMemberRole,
    expected_role: WorkspaceAccessRole,
) -> None:
    workspace = make_workspace()
    session = make_session((workspace, membership_role))
    repo = WorkspaceRepository(session)

    access = await repo.get_accessible_by_id(workspace.id, uuid4())

    assert access is not None
    assert access.role is expected_role


@pytest.mark.asyncio
async def test_get_accessible_workspace_returns_none_without_access() -> None:
    session = make_session(None)
    repo = WorkspaceRepository(session)

    access = await repo.get_accessible_by_id(uuid4(), uuid4())

    assert access is None
    session.execute.assert_awaited_once()
