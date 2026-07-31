from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from app.cache.task_list_cache import RedisTaskListCache
from app.core.enums import TaskPriority, TaskStatus
from app.schemas.task import TaskFilters, TaskPageResponse


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.incr_calls: list[str] = []
        self.unlink_calls: list[str] = []
        self.fail_operations: set[str] = set()

    def _raise_if_failed(self, operation: str) -> None:
        if operation in self.fail_operations:
            raise RedisError(f"{operation} failed")

    async def get(self, key: str) -> str | None:
        self._raise_if_failed("get")
        self.get_calls.append(key)
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> bool:
        self._raise_if_failed("set")
        self.set_calls.append((key, value, ex))
        self.values[key] = value
        return True

    async def incr(self, key: str) -> int:
        self._raise_if_failed("incr")
        self.incr_calls.append(key)
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def unlink(self, key: str) -> int:
        self._raise_if_failed("unlink")
        self.unlink_calls.append(key)
        return int(self.values.pop(key, None) is not None)


def make_cache(redis: FakeRedis, *, ttl_seconds: int = 60) -> RedisTaskListCache:
    return RedisTaskListCache(
        redis,  # type: ignore[arg-type]
        ttl_seconds=ttl_seconds,
    )


def make_response() -> TaskPageResponse:
    return TaskPageResponse(
        items=[],
        page=1,
        page_size=20,
        total=0,
        total_pages=0,
    )


@pytest.mark.asyncio
async def test_task_list_cache_round_trips_response_with_ttl() -> None:
    redis = FakeRedis()
    cache = make_cache(redis, ttl_seconds=45)
    project_id = uuid4()
    filters = TaskFilters(
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )
    response = make_response()

    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
        version="0",
        response=response,
    )
    cached = await cache.get(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
    )

    assert cached is not None
    assert cached.version == "0"
    assert cached.response == response
    assert len(redis.set_calls) == 1
    key, payload, ttl = redis.set_calls[0]
    assert key.startswith(f"taskhub:v1:project:{project_id}:tasks:list:v0:")
    assert payload == response.model_dump_json()
    assert ttl == 45


@pytest.mark.asyncio
async def test_task_list_cache_normalizes_equivalent_datetimes() -> None:
    redis = FakeRedis()
    cache = make_cache(redis)
    project_id = uuid4()
    response = make_response()
    utc_filters = TaskFilters(
        due_from=datetime(2026, 8, 1, tzinfo=UTC),
    )
    plus_seven_filters = TaskFilters(
        due_from=datetime(
            2026,
            8,
            1,
            7,
            tzinfo=timezone(timedelta(hours=7)),
        ),
    )

    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=utc_filters,
        version="0",
        response=response,
    )
    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=plus_seven_filters,
        version="0",
        response=response,
    )

    assert redis.set_calls[0][0] == redis.set_calls[1][0]


@pytest.mark.asyncio
async def test_task_list_cache_uses_distinct_keys_for_distinct_queries() -> None:
    redis = FakeRedis()
    cache = make_cache(redis)
    project_id = uuid4()
    response = make_response()

    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=TaskFilters(),
        version="0",
        response=response,
    )
    await cache.set(
        project_id,
        page=2,
        page_size=20,
        filters=TaskFilters(),
        version="0",
        response=response,
    )
    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=TaskFilters(unassigned=True),
        version="0",
        response=response,
    )

    assert len({call[0] for call in redis.set_calls}) == 3


@pytest.mark.asyncio
async def test_task_list_cache_invalidation_changes_version_namespace() -> None:
    redis = FakeRedis()
    cache = make_cache(redis)
    project_id = uuid4()
    response = make_response()

    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=TaskFilters(),
        version="0",
        response=response,
    )
    await cache.invalidate_project(project_id)
    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=TaskFilters(),
        version="1",
        response=response,
    )

    first_key, second_key = (call[0] for call in redis.set_calls)
    assert ":v0:" in first_key
    assert ":v1:" in second_key
    assert redis.incr_calls == [f"taskhub:v1:project:{project_id}:tasks:list:version"]


@pytest.mark.asyncio
async def test_task_list_cache_discards_invalid_payload() -> None:
    redis = FakeRedis()
    cache = make_cache(redis)
    project_id = uuid4()
    filters = TaskFilters()
    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
        version="0",
        response=make_response(),
    )
    key = redis.set_calls[0][0]
    redis.values[key] = "not-json"

    cached = await cache.get(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
    )

    assert cached is not None
    assert cached.version == "0"
    assert cached.response is None
    assert redis.unlink_calls == [key]
    assert key not in redis.values


@pytest.mark.parametrize("operation", ["get", "set", "incr"])
@pytest.mark.asyncio
async def test_task_list_cache_fails_open_on_redis_errors(
    operation: str,
) -> None:
    redis = FakeRedis()
    redis.fail_operations.add(operation)
    cache = make_cache(redis)
    project_id = uuid4()

    if operation == "get":
        assert (
            await cache.get(
                project_id,
                page=1,
                page_size=20,
                filters=TaskFilters(),
            )
            is None
        )
    elif operation == "set":
        version_key = f"taskhub:v1:project:{project_id}:tasks:list:version"
        redis.values[version_key] = "0"
        await cache.set(
            project_id,
            page=1,
            page_size=20,
            filters=TaskFilters(),
            version="0",
            response=make_response(),
        )
    else:
        await cache.invalidate_project(project_id)


@pytest.mark.asyncio
async def test_task_list_cache_writes_with_lookup_version_after_invalidation() -> None:
    redis = FakeRedis()
    cache = make_cache(redis)
    project_id = uuid4()
    filters = TaskFilters()

    lookup = await cache.get(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
    )
    assert lookup is not None
    assert lookup.version == "0"

    await cache.invalidate_project(project_id)
    await cache.set(
        project_id,
        page=1,
        page_size=20,
        filters=filters,
        version=lookup.version,
        response=make_response(),
    )

    assert ":tasks:list:v0:" in redis.set_calls[0][0]
    assert ":tasks:list:v1:" not in redis.set_calls[0][0]
