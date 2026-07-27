from collections.abc import Sequence
from uuid import UUID

from app.core.exceptions import EntityNotFoundException
from app.models.comment import Comment
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import CommentCreate, CommentUpdate


class CommentService:
    def __init__(self, repo: CommentRepository):
        self.repo = repo

    async def get_comment_by_id(self, comment_id: UUID) -> Comment:
        comment = await self.repo.get_by_id(comment_id)
        if not comment:
            raise EntityNotFoundException("Comment", comment_id)
        return comment

    async def get_task_comments(
        self,
        task_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Comment]:
        return await self.repo.get_by_task(
            task_id=task_id,
            skip=skip,
            limit=limit,
        )

    async def create_comment(self, comment_in: CommentCreate) -> Comment:
        return await self.repo.create(comment_in)

    async def update_comment(
        self,
        comment_id: UUID,
        comment_in: CommentUpdate,
    ) -> Comment:
        comment = await self.get_comment_by_id(comment_id)
        return await self.repo.update(comment, comment_in)

    async def delete_comment(self, comment_id: UUID) -> bool:
        await self.get_comment_by_id(comment_id)
        return await self.repo.delete(comment_id)
