from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import InactiveUserError, InvalidTokenError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def get_auth_repository(
    session: AsyncSession = Depends(get_db),
) -> AuthRepository:
    return AuthRepository(session)


def get_refresh_session_repository(
    session: AsyncSession = Depends(get_db),
) -> RefreshSessionRepository:
    return RefreshSessionRepository(session)


def get_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    refresh_session_repo: RefreshSessionRepository = Depends(
        get_refresh_session_repository
    ),
) -> AuthService:
    return AuthService(auth_repo, refresh_session_repo)


def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> UserRepository:
    return UserRepository(session)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo)


async def get_current_user(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    access_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not access_token:
        raise InvalidTokenError

    decoded = decode_token(access_token, TokenType.ACCESS)
    user = await user_repo.get_by_id(decoded.user_id)
    if user is None:
        raise InvalidTokenError
    if not user.is_active:
        raise InactiveUserError
    return user
