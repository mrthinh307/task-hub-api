from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base_repository import RepositoryBase


class LabelRepository(RepositoryBase[Label]):
    def __init__(self, session: AsyncSession):
        super().__init__(Label, session)
