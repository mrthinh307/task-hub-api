from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.enums import TokenType
from app.core.exceptions import ExpiredTokenError, InvalidTokenError
from app.core.security import (
    create_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.schemas.auth import RegisterRequest


def test_password_hash_and_verify() -> None:
    password = "correct-horse-battery-staple"

    hashed_password = get_password_hash(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)


def test_create_and_decode_access_token() -> None:
    user_id = uuid4()
    token, jti, expires_at = create_token(
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=15),
    )

    decoded = decode_token(token, TokenType.ACCESS)

    assert decoded.user_id == user_id
    assert decoded.jti == jti
    assert decoded.token_type is TokenType.ACCESS
    assert decoded.expires_at == expires_at.replace(microsecond=0)


def test_decode_rejects_wrong_token_type() -> None:
    token, _, _ = create_token(
        uuid4(),
        TokenType.ACCESS,
        timedelta(minutes=15),
    )

    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.REFRESH)


def test_decode_rejects_expired_token() -> None:
    token, _, _ = create_token(
        uuid4(),
        TokenType.REFRESH,
        timedelta(seconds=-1),
    )

    with pytest.raises(ExpiredTokenError):
        decode_token(token, TokenType.REFRESH)


def test_token_hash_is_deterministic_and_not_plaintext() -> None:
    token = "refresh-token-value"

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_register_password_rejects_more_than_72_bytes() -> None:
    with pytest.raises(ValueError):
        RegisterRequest(
            email="user@example.com",
            password="ă" * 37,
            full_name="Example User",
        )
