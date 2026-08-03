from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.dependencies import get_current_user, get_task_service
from app.core.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.task import (
    TaskCreate,
    TaskFilters,
    TaskPageResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])
project_task_router = APIRouter(
    prefix="/projects/{project_id}/tasks",
    tags=["Tasks"],
)


def get_task_filters(
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    assignee_id: Annotated[UUID | None, Query()] = None,
    unassigned: Annotated[bool, Query()] = False,
    created_by: Annotated[UUID | None, Query()] = None,
    due_from: Annotated[datetime | None, Query()] = None,
    due_to: Annotated[datetime | None, Query()] = None,
) -> TaskFilters:
    try:
        return TaskFilters(
            status=status_filter,
            priority=priority,
            assignee_id=assignee_id,
            unassigned=unassigned,
            created_by=created_by,
            due_from=due_from,
            due_to=due_to,
        )
    except ValidationError as exc:
        errors = [{**error, "loc": ("query", *error["loc"])} for error in exc.errors()]
        raise RequestValidationError(errors) from exc


@project_task_router.get(
    "",
    response_model=TaskPageResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def list_tasks(
    project_id: UUID,
    filters: Annotated[TaskFilters, Depends(get_task_filters)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> TaskPageResponse:
    return await service.list_tasks(
        project_id,
        current_user,
        page=page,
        page_size=page_size,
        filters=filters,
    )


@project_task_router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Task:
    return await service.create_task(project_id, current_user, payload)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Task:
    return await service.update_task(task_id, current_user, payload)
