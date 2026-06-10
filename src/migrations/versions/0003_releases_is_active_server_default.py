"""Releases: change is_active server default

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "releases",
        "is_active",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.false(),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "releases",
        "is_active",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.true(),
    )
