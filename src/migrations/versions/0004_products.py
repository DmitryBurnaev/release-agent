"""Products: partition releases by product.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the default product and attach existing releases to it."""
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.execute(sa.text("INSERT INTO products (name) VALUES ('default')"))
    op.add_column("releases", sa.Column("product_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE releases SET product_id = products.id "
            "FROM products WHERE products.name = 'default'"
        )
    )
    op.alter_column("releases", "product_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_releases_product_id_products",
        "releases",
        "products",
        ["product_id"],
        ["id"],
    )
    op.drop_constraint("releases_version_key", "releases", type_="unique")
    op.create_unique_constraint(
        "uq_releases_product_id_version", "releases", ["product_id", "version"]
    )
    op.create_index("ix_releases_product_id", "releases", ["product_id"])


def downgrade() -> None:
    """Restore the global release-version constraint."""
    op.drop_index("ix_releases_product_id", table_name="releases")
    op.drop_constraint("uq_releases_product_id_version", "releases", type_="unique")
    op.create_unique_constraint("releases_version_key", "releases", ["version"])
    op.drop_constraint("fk_releases_product_id_products", "releases", type_="foreignkey")
    op.drop_column("releases", "product_id")
    op.drop_table("products")
