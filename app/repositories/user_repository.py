from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base_repository import RepositoryBase


class UserRepository(RepositoryBase[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
