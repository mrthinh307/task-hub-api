from collections.abc import Sequence
from uuid import UUID

from app.core.exceptions import EntityAlreadyExistsException, EntityNotFoundException
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_user_by_id(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)
        return user

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[User]:
        return await self.repo.get_multi(skip=skip, limit=limit)

    async def create_user(self, user_in: UserCreate) -> User:
        existing_email = await self.repo.get_by_email(user_in.email)
        if existing_email:
            raise EntityAlreadyExistsException("User", "email", user_in.email)

        user_data = user_in.model_dump()
        raw_password = user_data.pop("password")
        user_data["hashed_password"] = get_password_hash(raw_password)

        return await self.repo.create(user_data)

    async def update_user(
        self,
        user_id: UUID,
        user_in: UserUpdate,
    ) -> User:
        user = await self.get_user_by_id(user_id)
        update_data = user_in.model_dump(exclude_unset=True)

        if update_data.get("password"):
            raw_password = update_data.pop("password")
            update_data["hashed_password"] = get_password_hash(raw_password)

        return await self.repo.update(user, update_data)

    async def delete_user(self, user_id: UUID) -> bool:
        await self.get_user_by_id(user_id)
        return await self.repo.delete(user_id)
