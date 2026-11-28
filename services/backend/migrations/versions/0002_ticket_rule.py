"""Her one-line fix rule on each ticket (additive).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("rule", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("tickets", "rule")
