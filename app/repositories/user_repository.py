from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base_repository import GetByIdRepository, UpdateRepository


class UserUpdateData(BaseModel):
    full_name: str | None = None
    hashed_password: str | None = None


class UserRepository(
    GetByIdRepository[User],
    UpdateRepository[User, UserUpdateData],
):
    """Persistence operations required by self-service user profiles."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
