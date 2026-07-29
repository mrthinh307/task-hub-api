from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.auth_repository import AuthRepository
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.services.auth_service import AuthService


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
