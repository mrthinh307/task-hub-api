from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base_repository import RepositoryBase


class LabelRepository(RepositoryBase[Label]):
    """Placeholder repository; compose capabilities when label features are added."""

    def __init__(self, session: AsyncSession):
        super().__init__(Label, session)
