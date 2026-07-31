import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import redis.asyncio as aioredis
from pydantic import ValidationError
from redis.exceptions import RedisError

from app.core.logging import logger
from app.schemas.task import TaskFilters, TaskPageResponse

KEY_PREFIX = "taskhub:v1:project"


@dataclass(frozen=True)
class TaskListCacheLookup:
    version: str
    response: TaskPageResponse | None


class TaskListCache(Protocol):
    async def get(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> TaskListCacheLookup | None: ...

    async def set(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
        version: str,
        response: TaskPageResponse,
    ) -> None: ...

    async def invalidate_project(self, project_id: UUID) -> None: ...


class RedisTaskListCache:
    def __init__(
        self,
        redis: aioredis.Redis,
        *,
        ttl_seconds: int,
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _version_key(project_id: UUID) -> str:
        return f"{KEY_PREFIX}:{project_id}:tasks:list:version"

    @staticmethod
    def _normalize_version(value: bytes | str | None) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return value or "0"

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat()

    @classmethod
    def _fingerprint(
        cls,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> str:
        query = {
            "assignee_id": (
                str(filters.assignee_id) if filters.assignee_id is not None else None
            ),
            "created_by": (
                str(filters.created_by) if filters.created_by is not None else None
            ),
            "due_from": cls._normalize_datetime(filters.due_from),
            "due_to": cls._normalize_datetime(filters.due_to),
            "page": page,
            "page_size": page_size,
            "priority": (
                filters.priority.value if filters.priority is not None else None
            ),
            "status": filters.status.value if filters.status is not None else None,
            "unassigned": filters.unassigned,
        }
        canonical_query = json.dumps(
            query,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical_query.encode()).hexdigest()

    @classmethod
    def _response_key(
        cls,
        project_id: UUID,
        *,
        version: str,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> str:
        fingerprint = cls._fingerprint(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        return f"{KEY_PREFIX}:{project_id}:tasks:list:v{version}:{fingerprint}"

    async def get(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
    ) -> TaskListCacheLookup | None:
        try:
            version = self._normalize_version(
                await self.redis.get(self._version_key(project_id))
            )
            key = self._response_key(
                project_id,
                version=version,
                page=page,
                page_size=page_size,
                filters=filters,
            )
            cached = await self.redis.get(key)
        except RedisError:
            logger.warning(
                "Failed to read task-list cache for project %s.",
                project_id,
                exc_info=True,
            )
            return None

        if cached is None:
            return TaskListCacheLookup(version=version, response=None)

        try:
            response = TaskPageResponse.model_validate_json(cached)
            return TaskListCacheLookup(version=version, response=response)
        except ValidationError:
            logger.warning(
                "Discarding invalid task-list cache payload for project %s.",
                project_id,
                exc_info=True,
            )
            try:
                await self.redis.unlink(key)
            except RedisError:
                logger.warning(
                    "Failed to remove invalid task-list cache key for project %s.",
                    project_id,
                    exc_info=True,
                )
            return TaskListCacheLookup(version=version, response=None)

    async def set(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        filters: TaskFilters,
        version: str,
        response: TaskPageResponse,
    ) -> None:
        try:
            key = self._response_key(
                project_id,
                version=version,
                page=page,
                page_size=page_size,
                filters=filters,
            )
            await self.redis.set(
                key,
                response.model_dump_json(),
                ex=self.ttl_seconds,
            )
        except RedisError:
            logger.warning(
                "Failed to write task-list cache for project %s.",
                project_id,
                exc_info=True,
            )

    async def invalidate_project(self, project_id: UUID) -> None:
        try:
            await self.redis.incr(self._version_key(project_id))
        except RedisError:
            logger.warning(
                "Failed to invalidate task-list cache for project %s.",
                project_id,
                exc_info=True,
            )
