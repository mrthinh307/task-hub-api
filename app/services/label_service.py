from collections.abc import Sequence
from uuid import UUID

from app.core.exceptions import EntityNotFoundException
from app.models.label import Label
from app.repositories.label_repository import LabelRepository
from app.schemas.label import LabelCreate, LabelUpdate


class LabelService:
    def __init__(self, repo: LabelRepository):
        self.repo = repo

    async def get_label_by_id(self, label_id: UUID) -> Label:
        label = await self.repo.get_by_id(label_id)
        if not label:
            raise EntityNotFoundException("Label", label_id)
        return label

    async def get_project_labels(self, project_id: UUID) -> Sequence[Label]:
        return await self.repo.get_by_project(project_id)

    async def create_label(self, label_in: LabelCreate) -> Label:
        return await self.repo.create(label_in)

    async def update_label(
        self,
        label_id: UUID,
        label_in: LabelUpdate,
    ) -> Label:
        label = await self.get_label_by_id(label_id)
        return await self.repo.update(label, label_in)

    async def delete_label(self, label_id: UUID) -> bool:
        await self.get_label_by_id(label_id)
        return await self.repo.delete(label_id)
