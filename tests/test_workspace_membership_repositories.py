from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkspaceMemberRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_member_repository import WorkspaceMemberRepository
from app.repositories.workspace_repository import WorkspaceRepository


def make_scalar_session(value: object) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_user_repository_gets_user_by_email() -> None:
    user = User(
        id=uuid4(),
        email="member@example.com",
        full_name="Workspace Member",
        hashed_password="not-used",
    )
    session = make_scalar_session(user)

    result = await UserRepository(session).get_by_email(user.email)

    assert result is user
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_workspace_repository_gets_workspace_only_for_owner() -> None:
    owner_id = uuid4()
    workspace = Workspace(
        id=uuid4(),
        name="Engineering",
        owner_id=owner_id,
    )
    session = make_scalar_session(workspace)

    result = await WorkspaceRepository(session).get_owned_by_id(
        workspace.id,
        owner_id,
    )

    assert result is workspace
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_workspace_member_repository_gets_membership() -> None:
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceMemberRole.VIEWER,
    )
    session = make_scalar_session(member)

    result = await WorkspaceMemberRepository(
        session
    ).get_by_workspace_and_user(member.workspace_id, member.user_id)

    assert result is member
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_workspace_member_repository_creates_and_flushes_membership() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    workspace_id = uuid4()
    user_id = uuid4()

    member = await WorkspaceMemberRepository(session).create_member(
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceMemberRole.EDITOR,
    )

    assert member.workspace_id == workspace_id
    assert member.user_id == user_id
    assert member.role is WorkspaceMemberRole.EDITOR
    session.add.assert_called_once_with(member)
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(member)
