from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_project_service
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "/workspace/{workspace_id}",
    response_model=Sequence[ProjectResponse],
)
async def get_workspace_projects(
    workspace_id: UUID,
    skip: int = 0,
    limit: int = 100,
    service: ProjectService = Depends(get_project_service),
):
    """Retrieve projects of a workspace."""
    return await service.get_workspace_projects(
        workspace_id=workspace_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def get_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
):
    """Get single project by ID."""
    return await service.get_project_by_id(project_id)


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    project_in: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
):
    """Create new project."""
    return await service.create_project(project_in)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
):
    """Update project information."""
    return await service.update_project(
        project_id=project_id,
        project_in=project_in,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
):
    """Delete a project."""
    await service.delete_project(project_id)
