from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.repositories.base_repository import RepositoryBase


class CommentRepository(RepositoryBase[Comment]):
    """Placeholder repository; compose capabilities when comment features are added."""

    def __init__(self, session: AsyncSession):
        super().__init__(Comment, session)
