from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.base_repository import (
    CreateRepository,
    DeleteRepository,
    GetByIdRepository,
    UpdateRepository,
)


class LabelCreateData(BaseModel):
    project_id: UUID
    name: str
    color: str


class LabelUpdateData(BaseModel):
    name: str | None = None
    color: str | None = None


class LabelRepository(
    GetByIdRepository[Label],
    CreateRepository[Label, LabelCreateData],
    UpdateRepository[Label, LabelUpdateData],
    DeleteRepository[Label],
):
    """Persistence operations required by label features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Label, session)

    async def list_by_project(self, project_id: UUID) -> Sequence[Label]:
        result = await self.session.execute(
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.name.asc(), Label.id.asc())
        )
        return result.scalars().all()

    async def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str,
    ) -> Label | None:
        result = await self.session.execute(
            select(Label).where(
                Label.project_id == project_id,
                Label.name == name,
            )
        )
        return result.scalar_one_or_none()
