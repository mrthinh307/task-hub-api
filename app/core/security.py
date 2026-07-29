from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import jwt
from jwt import ExpiredSignatureError
from jwt import InvalidTokenError as PyJWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import ExpiredTokenError, InvalidTokenError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class DecodedToken:
    user_id: UUID
    token_type: TokenType
    jti: UUID
    issued_at: datetime
    expires_at: datetime


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash of a password."""
    return pwd_context.hash(password)


def create_token(
    user_id: UUID,
    token_type: TokenType,
    expires_delta: timedelta,
) -> tuple[str, UUID, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = uuid4()
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "jti": str(jti),
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> DecodedToken:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "type", "jti", "iat", "exp"]},
        )
        token_type = TokenType(payload["type"])
        if token_type is not expected_type:
            raise InvalidTokenError
        return DecodedToken(
            user_id=UUID(payload["sub"]),
            token_type=token_type,
            jti=UUID(payload["jti"]),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError from exc
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError from exc


def hash_token(token: str) -> str:
    """Hash a refresh token before persisting or querying it."""
    return sha256(token.encode("utf-8")).hexdigest()
