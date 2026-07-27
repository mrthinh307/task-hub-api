from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_task_service
from app.core.enums import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get(
    "/",
    response_model=Sequence[TaskResponse],
)
async def get_tasks(
    project_id: UUID | None = None,
    assignee_id: UUID | None = None,
    status_filter: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    skip: int = 0,
    limit: int = 100,
    service: TaskService = Depends(get_task_service),
):
    """Retrieve tasks with optional filters."""
    return await service.get_tasks(
        project_id=project_id,
        assignee_id=assignee_id,
        status=status_filter,
        priority=priority,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
async def get_task(
    task_id: UUID,
    service: TaskService = Depends(get_task_service),
):
    """Get single task by ID."""
    return await service.get_task_by_id(task_id)


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    task_in: TaskCreate,
    service: TaskService = Depends(get_task_service),
):
    """Create new task."""
    return await service.create_task(task_in)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    task_id: UUID,
    task_in: TaskUpdate,
    service: TaskService = Depends(get_task_service),
):
    """Update task information."""
    return await service.update_task(
        task_id=task_id,
        task_in=task_in,
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task(
    task_id: UUID,
    service: TaskService = Depends(get_task_service),
):
    """Delete a task."""
    await service.delete_task(task_id)
