from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base_repository import BaseRepository
from app.schemas.label import LabelCreate, LabelUpdate


class LabelRepository(BaseRepository[Label, LabelCreate, LabelUpdate]):
    def __init__(self, session: AsyncSession):
        super().__init__(Label, session)

    async def get_by_project(
        self,
        project_id: UUID,
    ) -> Sequence[Label]:
        stmt = select(Label).where(Label.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
