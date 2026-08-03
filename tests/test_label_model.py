from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, UniqueConstraint

from app.models.label import Label
from app.models.task import Task, TaskLabel


def _unique_constraints(table: Table) -> dict[str, tuple[str, ...]]:
    return {
        str(constraint.name): tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_label_name_is_unique_within_project() -> None:
    constraints = _unique_constraints(cast(Table, Label.__table__))

    assert constraints["uq_labels_project_name"] == ("project_id", "name")


def test_task_cannot_have_the_same_label_twice() -> None:
    constraints = _unique_constraints(cast(Table, TaskLabel.__table__))

    assert constraints["uq_task_labels_task_label"] == ("task_id", "label_id")


def test_task_rejects_label_from_another_project() -> None:
    task = Task(project_id=uuid4(), created_by=uuid4(), title="Fix login")
    label = Label(project_id=uuid4(), name="backend")

    with pytest.raises(
        ValueError,
        match="Task and label must belong to the same project",
    ):
        task.labels.append(label)


def test_label_rejects_task_from_another_project() -> None:
    task = Task(project_id=uuid4(), created_by=uuid4(), title="Fix login")
    label = Label(project_id=uuid4(), name="backend")

    with pytest.raises(
        ValueError,
        match="Task and label must belong to the same project",
    ):
        label.tasks.append(task)


def test_task_accepts_label_from_same_project() -> None:
    project_id = uuid4()
    task = Task(project_id=project_id, created_by=uuid4(), title="Fix login")
    label = Label(project_id=project_id, name="backend")

    task.labels.append(label)

    assert task.labels == [label]
    assert label.tasks == [task]
