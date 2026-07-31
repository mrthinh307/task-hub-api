import asyncio

import pytest

from app.db import session as db_session
from app.db.post_commit import PostCommitActions


class FakeRedisClient:
    def __init__(self, *, ping_error: Exception | None = None) -> None:
        self.ping_error = ping_error
        self.ping_calls = 0
        self.close_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        await asyncio.sleep(0)
        if self.ping_error is not None:
            raise self.ping_error
        return True

    async def aclose(self) -> None:
        self.close_calls += 1


class FakeDatabaseSession:
    def __init__(
        self,
        events: list[str],
        *,
        commit_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.commit_error = commit_error

    async def __aenter__(self) -> "FakeDatabaseSession":
        self.events.append("enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        self.events.append("exit")

    async def commit(self) -> None:
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.events.append("rollback")

    async def close(self) -> None:
        self.events.append("close")


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


@pytest.mark.asyncio
async def test_concurrent_get_redis_calls_create_one_client(monkeypatch) -> None:
    created_clients: list[FakeRedisClient] = []

    def fake_from_url(*args, **kwargs) -> FakeRedisClient:
        client = FakeRedisClient()
        created_clients.append(client)
        return client

    async def resolve_client():
        dependency = db_session.get_redis()
        try:
            return await anext(dependency)
        finally:
            await dependency.aclose()

    monkeypatch.setattr(db_session, "redis_client", None)
    monkeypatch.setattr(db_session, "redis_init_lock", asyncio.Lock())
    monkeypatch.setattr(db_session.aioredis, "from_url", fake_from_url)

    clients = await asyncio.gather(*(resolve_client() for _ in range(10)))

    assert len(created_clients) == 1
    assert all(client is created_clients[0] for client in clients)


@pytest.mark.asyncio
async def test_get_db_runs_post_commit_actions_after_session_closes(
    monkeypatch,
) -> None:
    events: list[str] = []
    fake_session = FakeDatabaseSession(events)
    monkeypatch.setattr(
        db_session,
        "AsyncSessionLocal",
        lambda: fake_session,
    )
    actions = PostCommitActions()

    async def callback() -> None:
        events.append("callback")

    actions.add(callback)
    dependency = db_session.get_db(actions)

    assert await anext(dependency) is fake_session
    with pytest.raises(StopAsyncIteration):
        await anext(dependency)

    assert events == ["enter", "commit", "close", "exit", "callback"]


@pytest.mark.asyncio
async def test_get_db_does_not_run_post_commit_actions_after_rollback(
    monkeypatch,
) -> None:
    events: list[str] = []
    fake_session = FakeDatabaseSession(events)
    monkeypatch.setattr(
        db_session,
        "AsyncSessionLocal",
        lambda: fake_session,
    )
    actions = PostCommitActions()

    async def callback() -> None:
        events.append("callback")

    actions.add(callback)
    dependency = db_session.get_db(actions)
    await anext(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        await dependency.athrow(RuntimeError("request failed"))

    assert events == ["enter", "rollback", "close", "exit"]


@pytest.mark.asyncio
async def test_get_db_does_not_run_post_commit_actions_when_commit_fails(
    monkeypatch,
) -> None:
    events: list[str] = []
    fake_session = FakeDatabaseSession(
        events,
        commit_error=RuntimeError("commit failed"),
    )
    monkeypatch.setattr(
        db_session,
        "AsyncSessionLocal",
        lambda: fake_session,
    )
    actions = PostCommitActions()

    async def callback() -> None:
        events.append("callback")

    actions.add(callback)
    dependency = db_session.get_db(actions)
    await anext(dependency)

    with pytest.raises(RuntimeError, match="commit failed"):
        await anext(dependency)

    assert events == ["enter", "commit", "rollback", "close", "exit"]
