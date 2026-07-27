"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${up_revision | repr}
down_revision: Union[str, None] = ${None if down_revision in (None, 'None', '"None"') else repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${None if branch_labels in (None, 'None', '"None"') else repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${None if depends_on in (None, 'None', '"None"') else repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
