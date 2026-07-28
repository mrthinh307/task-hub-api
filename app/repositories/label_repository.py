from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base_repository import BaseRepository


class LabelRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(Label, session)
