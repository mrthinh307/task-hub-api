from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.task_label_repository import TaskLabelRepository


@pytest.mark.asyncio
async def test_add_task_label_uses_idempotent_postgresql_upsert() -> None:
    task_id = uuid4()
    label_id = uuid4()
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    repo = TaskLabelRepository(session)

    await repo.add(task_id, label_id)

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "INSERT INTO task_labels" in sql
    assert str(task_id) in sql
    assert str(label_id) in sql
    assert "ON CONFLICT ON CONSTRAINT uq_task_labels_task_label DO NOTHING" in sql
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_task_label_is_idempotent_and_does_not_commit() -> None:
    task_id = uuid4()
    label_id = uuid4()
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    repo = TaskLabelRepository(session)

    await repo.remove(task_id, label_id)

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "DELETE FROM task_labels" in sql
    assert f"task_labels.task_id = '{task_id}'" in sql
    assert f"task_labels.label_id = '{label_id}'" in sql
    session.commit.assert_not_awaited()
