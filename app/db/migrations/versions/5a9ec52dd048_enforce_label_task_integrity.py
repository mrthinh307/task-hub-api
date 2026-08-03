"""enforce label task integrity

Revision ID: 5a9ec52dd048
Revises: 1e23b067add5
Create Date: 2026-08-03 16:16:25.950976

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a9ec52dd048"
down_revision: str | None = "1e23b067add5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_labels_project_name",
        "labels",
        ["project_id", "name"],
    )
    op.create_unique_constraint(
        "uq_task_labels_task_label",
        "task_labels",
        ["task_id", "label_id"],
    )

    # A trigger cannot validate rows that predate it, so fail the migration instead
    # of silently preserving invalid cross-project associations.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM task_labels AS task_label
                JOIN tasks AS task ON task.id = task_label.task_id
                JOIN labels AS label ON label.id = task_label.label_id
                WHERE task.project_id <> label.project_id
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Existing task-label associations cross project boundaries',
                    CONSTRAINT = 'ck_task_labels_same_project';
            END IF;
        END
        $$;
        """
    )

    # Lock both parent rows while checking. This prevents concurrent project moves
    # from committing an invalid association between the check and the insert.
    op.execute(
        """
        CREATE FUNCTION taskhub_check_task_label_project()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            task_project_id uuid;
            label_project_id uuid;
        BEGIN
            SELECT project_id
            INTO task_project_id
            FROM tasks
            WHERE id = NEW.task_id
            FOR SHARE;

            SELECT project_id
            INTO label_project_id
            FROM labels
            WHERE id = NEW.label_id
            FOR SHARE;

            IF task_project_id IS NOT NULL
                AND label_project_id IS NOT NULL
                AND task_project_id <> label_project_id
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Task and label must belong to the same project',
                    CONSTRAINT = 'ck_task_labels_same_project';
            END IF;

            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_task_labels_same_project
        BEFORE INSERT OR UPDATE OF task_id, label_id ON task_labels
        FOR EACH ROW
        EXECUTE FUNCTION taskhub_check_task_label_project();
        """
    )

    # Guard parent project changes too; checking only task_labels writes would let
    # an existing valid association become invalid later.
    op.execute(
        """
        CREATE FUNCTION taskhub_check_task_project_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.project_id IS NOT DISTINCT FROM OLD.project_id THEN
                RETURN NEW;
            END IF;

            PERFORM 1
            FROM task_labels AS task_label
            JOIN labels AS label ON label.id = task_label.label_id
            WHERE task_label.task_id = NEW.id
                AND label.project_id <> NEW.project_id
            FOR SHARE OF label;

            IF FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Task and its labels must belong to the same project',
                    CONSTRAINT = 'ck_task_labels_same_project';
            END IF;

            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tasks_preserve_label_project
        BEFORE UPDATE OF project_id ON tasks
        FOR EACH ROW
        EXECUTE FUNCTION taskhub_check_task_project_change();
        """
    )

    op.execute(
        """
        CREATE FUNCTION taskhub_check_label_project_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.project_id IS NOT DISTINCT FROM OLD.project_id THEN
                RETURN NEW;
            END IF;

            PERFORM 1
            FROM task_labels AS task_label
            JOIN tasks AS task ON task.id = task_label.task_id
            WHERE task_label.label_id = NEW.id
                AND task.project_id <> NEW.project_id
            FOR SHARE OF task;

            IF FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Label and its tasks must belong to the same project',
                    CONSTRAINT = 'ck_task_labels_same_project';
            END IF;

            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_labels_preserve_task_project
        BEFORE UPDATE OF project_id ON labels
        FOR EACH ROW
        EXECUTE FUNCTION taskhub_check_label_project_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_labels_preserve_task_project ON labels")
    op.execute("DROP FUNCTION IF EXISTS taskhub_check_label_project_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_tasks_preserve_label_project ON tasks")
    op.execute("DROP FUNCTION IF EXISTS taskhub_check_task_project_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_task_labels_same_project ON task_labels")
    op.execute("DROP FUNCTION IF EXISTS taskhub_check_task_label_project()")
    op.drop_constraint(
        "uq_task_labels_task_label",
        "task_labels",
        type_="unique",
    )
    op.drop_constraint(
        "uq_labels_project_name",
        "labels",
        type_="unique",
    )
