from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_workspace_service
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get(
    "/user/{user_id}",
    response_model=Sequence[WorkspaceResponse],
)
async def get_user_workspaces(
    user_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Retrieve workspaces related to a user."""
    return await service.get_user_workspaces(user_id)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Get single workspace by ID."""
    return await service.get_workspace_by_id(workspace_id)


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    owner_id: UUID,
    workspace_in: WorkspaceCreate,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Create new workspace with owner."""
    return await service.create_workspace(
        owner_id=owner_id,
        workspace_in=workspace_in,
    )


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def update_workspace(
    workspace_id: UUID,
    workspace_in: WorkspaceUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Update workspace information."""
    return await service.update_workspace(
        workspace_id=workspace_id,
        workspace_in=workspace_in,
    )


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: UUID,
    member_in: WorkspaceMemberAdd,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Add a member to a workspace."""
    return await service.add_member(
        workspace_id=workspace_id,
        user_id=member_in.user_id,
        role=member_in.role,
    )


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
):
    """Delete a workspace."""
    await service.delete_workspace(workspace_id)
