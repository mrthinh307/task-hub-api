import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.enums import TokenType, UserRole
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import decode_token, hash_token
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService, TokenPair


class FakeDatabaseError(Exception):
    def __init__(self, sqlstate: str):
        self.sqlstate = sqlstate
        super().__init__(sqlstate)


class FakeAuthRepository(AuthRepository):
    def __init__(self):
        self.users_by_email = {}
        self.users_by_id = {}

    async def get_user_by_email(self, email: str):
        return self.users_by_email.get(email)

    async def get_by_id(self, entity_id: UUID):
        return self.users_by_id.get(entity_id)

    async def create_user(self, *, email, full_name, hashed_password):
        user = User(
            id=uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=UserRole.MEMBER,
            is_active=True,
        )
        self.users_by_email[email] = user
        self.users_by_id[user.id] = user
        return user


class FakeRefreshSessionRepository(RefreshSessionRepository):
    def __init__(self):
        self.sessions = {}
        self.refresh_lock = asyncio.Lock()

    async def create_session(self, *, user_id, token_hash, jti, expires_at):
        refresh_session = RefreshSession(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expires_at,
        )
        self.sessions[token_hash] = refresh_session
        return refresh_session

    async def get_by_token_hash_for_update(self, token_hash):
        await self.refresh_lock.acquire()
        return self.sessions.get(token_hash)

    async def rotate(
        self,
        current_session,
        *,
        new_token_hash,
        new_jti,
        new_expires_at,
        revoked_at,
    ):
        current_session.revoked_at = revoked_at
        replacement = await self.create_session(
            user_id=current_session.user_id,
            token_hash=new_token_hash,
            jti=new_jti,
            expires_at=new_expires_at,
        )
        current_session.replaced_by_id = replacement.id
        self.refresh_lock.release()
        return replacement

    async def revoke_by_token_hash(self, token_hash, *, revoked_at):
        refresh_session = self.sessions.get(token_hash)
        if refresh_session and refresh_session.revoked_at is None:
            refresh_session.revoked_at = revoked_at


@pytest.fixture
def service():
    auth_repo = FakeAuthRepository()
    refresh_repo = FakeRefreshSessionRepository()
    return AuthService(auth_repo, refresh_repo), auth_repo, refresh_repo


@pytest.mark.asyncio
async def test_register_creates_user_and_authenticated_session(service) -> None:
    auth_service, auth_repo, refresh_repo = service

    result = await auth_service.register(
        RegisterRequest(
            email="USER@example.com",
            password="password123",
            full_name="Example User",
        )
    )

    assert result.user.email == "user@example.com"
    assert result.user.hashed_password != "password123"
    assert result.user.role is UserRole.MEMBER
    assert result.user.is_active
    assert auth_repo.users_by_email[result.user.email] is result.user
    assert hash_token(result.tokens.refresh_token) in refresh_repo.sessions
    assert (
        decode_token(result.tokens.access_token, TokenType.ACCESS).user_id
        == result.user.id
    )


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(service) -> None:
    auth_service, _, _ = service
    payload = RegisterRequest(
        email="user@example.com",
        password="password123",
        full_name="Example User",
    )
    await auth_service.register(payload)

    with pytest.raises(EmailAlreadyRegisteredError):
        await auth_service.register(payload)


@pytest.mark.asyncio
async def test_register_maps_unique_violation_to_duplicate_email(service) -> None:
    auth_service, auth_repo, _ = service

    async def raise_unique_violation(**kwargs):
        raise IntegrityError(
            statement=None,
            params=None,
            orig=FakeDatabaseError("23505"),
        )

    auth_repo.create_user = raise_unique_violation

    with pytest.raises(EmailAlreadyRegisteredError):
        await auth_service.register(
            RegisterRequest(
                email="user@example.com",
                password="password123",
                full_name="Example User",
            )
        )


@pytest.mark.asyncio
async def test_register_does_not_mask_other_integrity_errors(service) -> None:
    auth_service, auth_repo, _ = service

    async def raise_foreign_key_violation(**kwargs):
        raise IntegrityError(
            statement=None,
            params=None,
            orig=FakeDatabaseError("23503"),
        )

    auth_repo.create_user = raise_foreign_key_violation

    with pytest.raises(IntegrityError):
        await auth_service.register(
            RegisterRequest(
                email="user@example.com",
                password="password123",
                full_name="Example User",
            )
        )


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(service) -> None:
    auth_service, _, _ = service

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login(
            LoginRequest(email="missing@example.com", password="password123")
        )


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(service) -> None:
    auth_service, _, _ = service
    registered = await auth_service.register(
        RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Example User",
        )
    )
    registered.user.is_active = False

    with pytest.raises(InactiveUserError):
        await auth_service.login(
            LoginRequest(email="user@example.com", password="password123")
        )


@pytest.mark.asyncio
async def test_refresh_rotates_and_rejects_replay(service) -> None:
    auth_service, _, refresh_repo = service
    registered = await auth_service.register(
        RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Example User",
        )
    )
    old_token = registered.tokens.refresh_token
    old_session = refresh_repo.sessions[hash_token(old_token)]

    new_tokens = await auth_service.refresh(old_token)

    assert old_session.revoked_at is not None
    assert old_session.replaced_by_id is not None
    assert hash_token(new_tokens.refresh_token) in refresh_repo.sessions
    with pytest.raises(InvalidTokenError):
        await auth_service.refresh(old_token)


@pytest.mark.asyncio
async def test_concurrent_refresh_allows_only_one_rotation(service) -> None:
    auth_service, _, _ = service
    registered = await auth_service.register(
        RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Example User",
        )
    )

    results = await asyncio.gather(
        auth_service.refresh(registered.tokens.refresh_token),
        auth_service.refresh(registered.tokens.refresh_token),
        return_exceptions=True,
    )

    assert sum(isinstance(result, TokenPair) for result in results) == 1
    assert sum(isinstance(result, InvalidTokenError) for result in results) == 1


@pytest.mark.asyncio
async def test_logout_revokes_current_session_and_is_idempotent(service) -> None:
    auth_service, _, refresh_repo = service
    registered = await auth_service.register(
        RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Example User",
        )
    )
    token = registered.tokens.refresh_token
    refresh_session = refresh_repo.sessions[hash_token(token)]

    await auth_service.logout(token)
    first_revoked_at = refresh_session.revoked_at
    await auth_service.logout(token)
    await auth_service.logout(None)

    assert isinstance(first_revoked_at, datetime)
    assert first_revoked_at.tzinfo is UTC
    assert refresh_session.revoked_at == first_revoked_at
