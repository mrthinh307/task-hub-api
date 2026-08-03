from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_comment_service, get_current_user
from app.models.comment import Comment
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.errors import ErrorResponse
from app.services.comment_service import CommentService

router = APIRouter(prefix="/comments", tags=["Comments"])
task_comment_router = APIRouter(
    prefix="/tasks/{task_id}/comments",
    tags=["Comments"],
)


@task_comment_router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def add_comment(
    task_id: UUID,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> Comment:
    return await service.add_comment(task_id, current_user, payload)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def delete_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> None:
    await service.delete_comment(comment_id, current_user)
