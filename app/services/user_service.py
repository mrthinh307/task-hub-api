from app.core.exceptions import (
    InvalidCurrentPasswordError,
    PasswordUnchangedError,
)
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository, UserUpdateData
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def get_profile(self, current_user: User) -> User:
        return current_user

    async def update_profile(
        self,
        current_user: User,
        payload: UserUpdate,
    ) -> User:
        update_data: dict[str, str] = {}
        if payload.full_name is not None:
            update_data["full_name"] = payload.full_name

        if payload.new_password is not None:
            assert payload.current_password is not None
            if not verify_password(
                payload.current_password,
                current_user.hashed_password,
            ):
                raise InvalidCurrentPasswordError
            if verify_password(
                payload.new_password,
                current_user.hashed_password,
            ):
                raise PasswordUnchangedError
            update_data["hashed_password"] = get_password_hash(payload.new_password)

        return await self.repo.update(
            current_user,
            UserUpdateData(**update_data),
        )
