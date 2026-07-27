from collections.abc import Sequence

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_user_service
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=Sequence[UserResponse])
async def get_users(
    skip: int = 0, limit: int = 100, service: UserService = Depends(get_user_service)
):
    """Retrieve list of users with pagination."""
    return await service.get_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    """Get single user by ID."""
    return await service.get_user_by_id(user_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate, service: UserService = Depends(get_user_service)
):
    """Create new user."""
    return await service.create_user(user_in)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, user_in: UserUpdate, service: UserService = Depends(get_user_service)
):
    """Update user information."""
    return await service.update_user(user_id, user_in)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, service: UserService = Depends(get_user_service)):
    """Delete a user."""
    await service.delete_user(user_id)
