from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.task_repository import TaskFilterData, TaskRepository


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
        filters=TaskFilterData(),
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


@pytest.mark.asyncio
async def test_list_by_project_applies_filters_to_count_and_page_queries() -> None:
    project_id = uuid4()
    assignee_id = uuid4()
    creator_id = uuid4()
    due_from = datetime(2026, 8, 1, tzinfo=UTC)
    due_to = datetime(2026, 8, 31, 23, 59, tzinfo=UTC)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    tasks_result = MagicMock()
    tasks_result.scalars.return_value.all.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[count_result, tasks_result])
    repo = TaskRepository(session)

    await repo.list_by_project(
        project_id,
        filters=TaskFilterData(
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee_id=assignee_id,
            created_by=creator_id,
            due_from=due_from,
            due_to=due_to,
        ),
        offset=0,
        limit=20,
    )

    statements = [
        str(
            call.args[0].compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for call in session.execute.await_args_list
    ]
    for statement in statements:
        assert f"tasks.project_id = '{project_id}'" in statement
        assert "tasks.status = 'IN_PROGRESS'" in statement
        assert "tasks.priority = 'HIGH'" in statement
        assert f"tasks.assignee_id = '{assignee_id}'" in statement
        assert f"tasks.created_by = '{creator_id}'" in statement
        assert "tasks.due_date >=" in statement
        assert "tasks.due_date <=" in statement


@pytest.mark.asyncio
async def test_list_by_project_filters_unassigned_tasks() -> None:
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    tasks_result = MagicMock()
    tasks_result.scalars.return_value.all.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[count_result, tasks_result])
    repo = TaskRepository(session)

    await repo.list_by_project(
        uuid4(),
        filters=TaskFilterData(unassigned=True),
        offset=0,
        limit=20,
    )

    for call in session.execute.await_args_list:
        statement = str(
            call.args[0].compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        assert "tasks.assignee_id IS NULL" in statement
