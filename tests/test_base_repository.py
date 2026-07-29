from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.base_repository import (
    BaseRepository,
    CreateRepository,
    DeleteRepository,
    GetByIdRepository,
    ListRepository,
    RepositoryBase,
    UpdateRepository,
)


class UserCreateInput(BaseModel):
    email: str
    full_name: str
    hashed_password: str
    role: UserRole = UserRole.MEMBER
    is_active: bool = True


class UserUpdateInput(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class UnknownFieldInput(BaseModel):
    unknown: str


class FullUserRepository(
    BaseRepository[User, UserCreateInput, UserUpdateInput],
):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)


def make_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


def make_user() -> User:
    return User(
        id=uuid4(),
        email="user@example.com",
        full_name="Example User",
        hashed_password="hashed-password",
        role=UserRole.MEMBER,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_get_by_id_capability_is_model_typed() -> None:
    session = make_session()
    user = make_user()
    session.get.return_value = user
    repo = GetByIdRepository[User](User, session)

    result = await repo.get_by_id(user.id)

    assert result is user
    session.get.assert_awaited_once_with(User, user.id)


@pytest.mark.asyncio
async def test_list_capability_returns_models() -> None:
    session = make_session()
    user = make_user()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [user]
    session.execute.return_value = result
    repo = ListRepository[User](User, session)

    users = await repo.get_multi(skip=5, limit=10)

    assert users == [user]
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_capability_accepts_schema_and_can_skip_refresh() -> None:
    session = make_session()
    repo = CreateRepository[User, UserCreateInput](User, session)
    payload = UserCreateInput(
        email="user@example.com",
        full_name="Example User",
        hashed_password="hashed-password",
    )

    user = await repo.create(payload, refresh=False)

    assert user.email == payload.email
    assert user.role is UserRole.MEMBER
    session.add.assert_called_once_with(user)
    session.flush.assert_awaited_once()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_applies_explicit_none_and_false_values() -> None:
    session = make_session()
    repo = UpdateRepository[User, UserUpdateInput](User, session)
    user = make_user()

    result = await repo.update(
        user,
        UserUpdateInput(full_name=None, is_active=False),
    )

    assert result is user
    assert user.full_name is None
    assert user.is_active is False
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_update_rejects_unknown_model_fields() -> None:
    session = make_session()
    repo = UpdateRepository[User, UnknownFieldInput](User, session)

    with pytest.raises(ValueError, match="Unknown model fields: unknown"):
        await repo.update(make_user(), UnknownFieldInput(unknown="value"))

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_capability_handles_found_and_missing_models() -> None:
    session = make_session()
    user = make_user()
    session.get.side_effect = [user, None]
    repo = DeleteRepository[User](User, session)

    assert await repo.delete(user.id)
    assert not await repo.delete(uuid4())
    session.delete.assert_awaited_once_with(user)
    session.flush.assert_awaited_once()


def test_full_base_repository_composes_all_capabilities() -> None:
    repo = FullUserRepository(make_session())

    assert isinstance(repo, RepositoryBase)
    assert callable(repo.get_by_id)
    assert callable(repo.get_multi)
    assert callable(repo.create)
    assert callable(repo.update)
    assert callable(repo.delete)


@pytest.mark.asyncio
async def test_auth_repository_reuses_get_and_create_capabilities() -> None:
    session = make_session()
    user = make_user()
    session.get.return_value = user
    repo = AuthRepository(session)

    found = await repo.get_by_id(user.id)
    created = await repo.create_user(
        email="new@example.com",
        full_name="New User",
        hashed_password="new-hashed-password",
    )

    assert found is user
    assert created.email == "new@example.com"
    assert created.role is UserRole.MEMBER
    session.get.assert_awaited_once_with(User, user.id)
    session.add.assert_called_once_with(created)
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created)
