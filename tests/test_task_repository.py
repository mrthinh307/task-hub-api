from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.task_repository import TaskRepository


@pytest.mark.asyncio
async def test_list_by_project_returns_stable_paginated_result() -> None:
    project_id = uuid4()
    now = datetime.now(UTC)
    tasks = [
        Task(
            id=uuid4(),
            project_id=project_id,
            assignee_id=None,
            created_by=uuid4(),
            title=f"Task {index}",
            description=None,
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            due_date=None,
            created_at=now,
            updated_at=now,
        )
        for index in range(2)
    ]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 5
    tasks_result = MagicMock()
    tasks_result.scalars.return_value.all.return_value = tasks
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[count_result, tasks_result])
    repo = TaskRepository(session)

    result = await repo.list_by_project(
        project_id,
        offset=2,
        limit=2,
    )

    assert list(result.items) == tasks
    assert result.total == 5
    assert session.execute.await_count == 2

    count_statement = session.execute.await_args_list[0].args[0]
    page_statement = session.execute.await_args_list[1].args[0]
    count_sql = str(
        count_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    page_sql = str(
        page_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "count(tasks.id)" in count_sql
    assert f"WHERE tasks.project_id = '{project_id}'" in count_sql
    assert f"WHERE tasks.project_id = '{project_id}'" in page_sql
    assert "ORDER BY tasks.created_at DESC, tasks.id DESC" in page_sql
    assert "LIMIT 2 OFFSET 2" in page_sql
