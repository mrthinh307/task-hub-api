from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.repositories.base_repository import (
    CreateRepository,
    DeleteRepository,
    GetByIdRepository,
)


class CommentCreateData(BaseModel):
    task_id: UUID
    author_id: UUID
    content: str


class CommentRepository(
    GetByIdRepository[Comment],
    CreateRepository[Comment, CommentCreateData],
    DeleteRepository[Comment],
):
    """Persistence operations required by comment features."""

    def __init__(self, session: AsyncSession):
        super().__init__(Comment, session)
