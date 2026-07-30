from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.enums import UserRole
from app.core.exceptions import (
    InvalidCurrentPasswordError,
    PasswordUnchangedError,
)
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user_repository import UserUpdateData
from app.schemas.user import UserUpdate
from app.services.user_service import UserService


class FakeUserRepository:
    def __init__(self) -> None:
        self.update_calls: list[dict[str, str | None]] = []

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


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="user@example.com",
        full_name="Example User",
        hashed_password=get_password_hash("password123"),
        role=UserRole.MEMBER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_profile_changes_only_full_name() -> None:
    repo = FakeUserRepository()
    service = UserService(repo)  # type: ignore[arg-type]
    user = make_user()
    old_password_hash = user.hashed_password

    result = await service.update_profile(
        user,
        UserUpdate(full_name="  Updated User  "),
    )

    assert result is user
    assert user.full_name == "Updated User"
    assert user.hashed_password == old_password_hash
    assert repo.update_calls == [{"full_name": "Updated User"}]


@pytest.mark.asyncio
async def test_update_profile_hashes_new_password() -> None:
    repo = FakeUserRepository()
    service = UserService(repo)  # type: ignore[arg-type]
    user = make_user()

    await service.update_profile(
        user,
        UserUpdate(
            current_password="password123",
            new_password="new-password-456",
        ),
    )

    assert user.hashed_password != "new-password-456"
    assert verify_password("new-password-456", user.hashed_password)
    assert set(repo.update_calls[0]) == {"hashed_password"}


@pytest.mark.asyncio
async def test_failed_password_confirmation_does_not_apply_name_update() -> None:
    repo = FakeUserRepository()
    service = UserService(repo)  # type: ignore[arg-type]
    user = make_user()

    with pytest.raises(InvalidCurrentPasswordError):
        await service.update_profile(
            user,
            UserUpdate(
                full_name="Must Not Change",
                current_password="wrong-password",
                new_password="new-password-456",
            ),
        )

    assert user.full_name == "Example User"
    assert repo.update_calls == []


@pytest.mark.asyncio
async def test_update_profile_rejects_reused_password() -> None:
    repo = FakeUserRepository()
    service = UserService(repo)  # type: ignore[arg-type]
    user = make_user()

    with pytest.raises(PasswordUnchangedError):
        await service.update_profile(
            user,
            UserUpdate(
                current_password="password123",
                new_password="password123",
            ),
        )

    assert repo.update_calls == []
