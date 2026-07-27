from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.repositories.base_repository import BaseRepository
from app.schemas.comment import CommentCreate, CommentUpdate


class CommentRepository(BaseRepository[Comment, CommentCreate, CommentUpdate]):
    def __init__(self, session: AsyncSession):
        super().__init__(Comment, session)

    async def get_by_task(
        self,
        task_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Comment]:
        stmt = (
            select(Comment).where(Comment.task_id == task_id).offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
