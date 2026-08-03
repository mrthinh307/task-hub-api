from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.repositories.label_repository import LabelRepository


@pytest.mark.asyncio
async def test_list_by_project_orders_labels_stably() -> None:
    project_id = uuid4()
    now = datetime.now(UTC)
    labels = [
        Label(
            id=uuid4(),
            project_id=project_id,
            name="backend",
            color="#2563EB",
            created_at=now,
            updated_at=now,
        )
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = labels
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repo = LabelRepository(session)

    loaded = await repo.list_by_project(project_id)

    assert list(loaded) == labels
    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert f"WHERE labels.project_id = '{project_id}'" in sql
    assert "ORDER BY labels.name ASC, labels.id ASC" in sql


@pytest.mark.asyncio
async def test_get_by_project_and_name_scopes_lookup_to_project() -> None:
    project_id = uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repo = LabelRepository(session)

    loaded = await repo.get_by_project_and_name(project_id, "backend")

    assert loaded is None
    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert f"labels.project_id = '{project_id}'" in sql
    assert "labels.name = 'backend'" in sql
