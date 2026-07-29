from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.models.user import User
from app.repositories.base_repository import (
    CreateRepository,
    GetByIdRepository,
)


class AuthUserCreate(BaseModel):
    email: str
    full_name: str
    hashed_password: str
    role: UserRole = UserRole.MEMBER
    is_active: bool = True


class AuthRepository(
    GetByIdRepository[User],
    CreateRepository[User, AuthUserCreate],
):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
    ) -> User:
        return await self.create(
            AuthUserCreate(
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
            )
        )
