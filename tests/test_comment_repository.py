from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.repositories.comment_repository import CommentCreateData, CommentRepository


@pytest.mark.asyncio
async def test_create_comment_flushes_without_committing() -> None:
    task_id = uuid4()
    author_id = uuid4()
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    repo = CommentRepository(session)

    comment = await repo.create(
        CommentCreateData(
            task_id=task_id,
            author_id=author_id,
            content="Looks good",
        )
    )

    assert comment.task_id == task_id
    assert comment.author_id == author_id
    assert comment.content == "Looks good"
    session.add.assert_called_once_with(comment)
    session.flush.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(comment)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_comment_flushes_without_committing() -> None:
    comment = Comment(
        id=uuid4(),
        task_id=uuid4(),
        author_id=uuid4(),
        content="Delete me",
    )
    session = MagicMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=comment)
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    repo = CommentRepository(session)

    deleted = await repo.delete(comment.id)

    assert deleted
    session.get.assert_awaited_once_with(Comment, comment.id)
    session.delete.assert_awaited_once_with(comment)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()
