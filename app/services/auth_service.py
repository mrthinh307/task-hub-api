from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.schemas.auth import LoginRequest, RegisterRequest


def _is_unique_violation(exc: IntegrityError) -> bool:
    """Return whether PostgreSQL reported a unique-constraint violation."""
    return getattr(exc.orig, "sqlstate", None) == "23505"


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class AuthResult:
    user: User
    tokens: TokenPair


class AuthService:
    def __init__(
        self,
        auth_repo: AuthRepository,
        refresh_session_repo: RefreshSessionRepository,
    ):
        self.auth_repo = auth_repo
        self.refresh_session_repo = refresh_session_repo

    async def register(self, payload: RegisterRequest) -> AuthResult:
        email = str(payload.email).lower()
        if await self.auth_repo.get_user_by_email(email):
            raise EmailAlreadyRegisteredError

        try:
            user = await self.auth_repo.create_user(
                email=email,
                full_name=payload.full_name,
                hashed_password=get_password_hash(payload.password),
            )
        except IntegrityError as exc:
            if not _is_unique_violation(exc):
                raise
            raise EmailAlreadyRegisteredError from exc

        tokens = await self._create_session(user)
        return AuthResult(user=user, tokens=tokens)

    async def login(self, payload: LoginRequest) -> AuthResult:
        email = str(payload.email).lower()
        user = await self.auth_repo.get_user_by_email(email)
        if user is None or not verify_password(
            payload.password,
            user.hashed_password,
        ):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError

        tokens = await self._create_session(user)
        return AuthResult(user=user, tokens=tokens)

    async def refresh(self, refresh_token: str) -> TokenPair:
        decoded = decode_token(refresh_token, TokenType.REFRESH)
        token_digest = hash_token(refresh_token)
        refresh_session = await self.refresh_session_repo.get_by_token_hash_for_update(
            token_digest
        )
        now = datetime.now(UTC)
        refresh_session = self._validate_refresh_session(
            refresh_session,
            expected_user_id=decoded.user_id,
            expected_jti=decoded.jti,
            now=now,
        )

        user = await self.auth_repo.get_by_id(decoded.user_id)
        if user is None:
            raise InvalidTokenError
        if not user.is_active:
            raise InactiveUserError

        access_token, _, _ = create_token(
            user.id,
            TokenType.ACCESS,
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        new_refresh_token, new_jti, new_expires_at = create_token(
            user.id,
            TokenType.REFRESH,
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.refresh_session_repo.rotate(
            refresh_session,
            new_token_hash=hash_token(new_refresh_token),
            new_jti=new_jti,
            new_expires_at=new_expires_at,
            revoked_at=now,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        await self.refresh_session_repo.revoke_by_token_hash(
            hash_token(refresh_token),
            revoked_at=datetime.now(UTC),
        )

    async def _create_session(self, user: User) -> TokenPair:
        access_token, _, _ = create_token(
            user.id,
            TokenType.ACCESS,
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token, refresh_jti, refresh_expires_at = create_token(
            user.id,
            TokenType.REFRESH,
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.refresh_session_repo.create_session(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            jti=refresh_jti,
            expires_at=refresh_expires_at,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    @staticmethod
    def _validate_refresh_session(
        refresh_session: RefreshSession | None,
        *,
        expected_user_id: UUID,
        expected_jti: UUID,
        now: datetime,
    ) -> RefreshSession:
        if (
            refresh_session is None
            or refresh_session.user_id != expected_user_id
            or refresh_session.jti != expected_jti
            or refresh_session.revoked_at is not None
            or refresh_session.expires_at <= now
        ):
            raise InvalidTokenError
        return refresh_session
