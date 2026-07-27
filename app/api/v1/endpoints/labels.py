from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_label_service
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.services.label_service import LabelService

router = APIRouter(prefix="/labels", tags=["Labels"])


@router.get(
    "/project/{project_id}",
    response_model=Sequence[LabelResponse],
)
async def get_project_labels(
    project_id: UUID,
    service: LabelService = Depends(get_label_service),
):
    """Retrieve labels of a project."""
    return await service.get_project_labels(project_id)


@router.get(
    "/{label_id}",
    response_model=LabelResponse,
)
async def get_label(
    label_id: UUID,
    service: LabelService = Depends(get_label_service),
):
    """Get single label by ID."""
    return await service.get_label_by_id(label_id)


@router.post(
    "/",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_label(
    label_in: LabelCreate,
    service: LabelService = Depends(get_label_service),
):
    """Create new label."""
    return await service.create_label(label_in)


@router.put(
    "/{label_id}",
    response_model=LabelResponse,
)
async def update_label(
    label_id: UUID,
    label_in: LabelUpdate,
    service: LabelService = Depends(get_label_service),
):
    """Update label information."""
    return await service.update_label(
        label_id=label_id,
        label_in=label_in,
    )


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_label(
    label_id: UUID,
    service: LabelService = Depends(get_label_service),
):
    """Delete a label."""
    await service.delete_label(label_id)
