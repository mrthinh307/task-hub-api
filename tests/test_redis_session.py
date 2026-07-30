import pytest

from app.db import session as db_session


class FakeRedisClient:
    def __init__(self, *, ping_error: Exception | None = None) -> None:
        self.ping_error = ping_error
        self.ping_calls = 0
        self.close_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        if self.ping_error is not None:
            raise self.ping_error
        return True

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_init_redis_verifies_and_reuses_shared_client(monkeypatch) -> None:
    fake_client = FakeRedisClient()
    captured_kwargs: dict[str, object] = {}

    def fake_from_url(url: str, **kwargs: object) -> FakeRedisClient:
        captured_kwargs["url"] = url
        captured_kwargs.update(kwargs)
        return fake_client

    monkeypatch.setattr(db_session, "redis_client", None)
    monkeypatch.setattr(db_session.aioredis, "from_url", fake_from_url)

    first_client = await db_session.init_redis()
    second_client = await db_session.init_redis()

    assert first_client is fake_client
    assert second_client is fake_client
    assert fake_client.ping_calls == 1
    assert captured_kwargs == {
        "url": db_session.settings.REDIS_URL,
        "encoding": "utf-8",
        "decode_responses": True,
        "max_connections": db_session.settings.REDIS_MAX_CONNECTIONS,
        "socket_connect_timeout": (
            db_session.settings.REDIS_SOCKET_CONNECT_TIMEOUT
        ),
        "socket_timeout": db_session.settings.REDIS_SOCKET_TIMEOUT,
        "health_check_interval": db_session.settings.REDIS_HEALTH_CHECK_INTERVAL,
        "retry_on_timeout": True,
    }

    await db_session.close_redis()

    assert fake_client.close_calls == 1
    assert db_session.redis_client is None


@pytest.mark.asyncio
async def test_init_redis_closes_failed_client(monkeypatch) -> None:
    fake_client = FakeRedisClient(ping_error=RuntimeError("Redis unavailable"))

    monkeypatch.setattr(db_session, "redis_client", None)
    monkeypatch.setattr(
        db_session.aioredis,
        "from_url",
        lambda *args, **kwargs: fake_client,
    )

    with pytest.raises(RuntimeError, match="Redis unavailable"):
        await db_session.init_redis()

    assert fake_client.ping_calls == 1
    assert fake_client.close_calls == 1
    assert db_session.redis_client is None
