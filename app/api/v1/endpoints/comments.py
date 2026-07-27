from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_comment_service
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.services.comment_service import CommentService

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.get(
    "/task/{task_id}",
    response_model=Sequence[CommentResponse],
)
async def get_task_comments(
    task_id: UUID,
    skip: int = 0,
    limit: int = 100,
    service: CommentService = Depends(get_comment_service),
):
    """Retrieve comments of a task."""
    return await service.get_task_comments(
        task_id=task_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
)
async def get_comment(
    comment_id: UUID,
    service: CommentService = Depends(get_comment_service),
):
    """Get single comment by ID."""
    return await service.get_comment_by_id(comment_id)


@router.post(
    "/",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    comment_in: CommentCreate,
    service: CommentService = Depends(get_comment_service),
):
    """Create new comment."""
    return await service.create_comment(comment_in)


@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
)
async def update_comment(
    comment_id: UUID,
    comment_in: CommentUpdate,
    service: CommentService = Depends(get_comment_service),
):
    """Update comment content."""
    return await service.update_comment(
        comment_id=comment_id,
        comment_in=comment_in,
    )


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    comment_id: UUID,
    service: CommentService = Depends(get_comment_service),
):
    """Delete a comment."""
    await service.delete_comment(comment_id)
