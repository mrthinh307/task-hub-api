from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_user,
    get_label_service,
    get_task_label_service,
)
from app.models.label import Label
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.services.label_service import LabelService
from app.services.task_label_service import TaskLabelService

router = APIRouter(prefix="/labels", tags=["Labels"])
project_label_router = APIRouter(
    prefix="/projects/{project_id}/labels",
    tags=["Labels"],
)
task_label_router = APIRouter(
    prefix="/tasks/{task_id}/labels",
    tags=["Labels"],
)


@project_label_router.post(
    "",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def create_label(
    project_id: UUID,
    payload: LabelCreate,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> Label:
    return await service.create_label(project_id, current_user, payload)


@project_label_router.get(
    "",
    response_model=list[LabelResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def list_labels(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> Sequence[Label]:
    return await service.list_labels(project_id, current_user)


@router.get(
    "/{label_id}",
    response_model=LabelResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def get_label(
    label_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> Label:
    return await service.get_label(label_id, current_user)


@router.patch(
    "/{label_id}",
    response_model=LabelResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def update_label(
    label_id: UUID,
    payload: LabelUpdate,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> Label:
    return await service.update_label(label_id, current_user, payload)


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def delete_label(
    label_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LabelService = Depends(get_label_service),
) -> None:
    await service.delete_label(label_id, current_user)


@task_label_router.put(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def assign_label_to_task(
    task_id: UUID,
    label_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TaskLabelService = Depends(get_task_label_service),
) -> None:
    await service.assign_label(task_id, label_id, current_user)


@task_label_router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def remove_label_from_task(
    task_id: UUID,
    label_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TaskLabelService = Depends(get_task_label_service),
) -> None:
    await service.remove_label(task_id, label_id, current_user)
