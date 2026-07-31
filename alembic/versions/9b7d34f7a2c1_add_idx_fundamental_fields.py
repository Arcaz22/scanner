"""add idx fundamental fields

Revision ID: 9b7d34f7a2c1
Revises: 85f5756f3951
Create Date: 2026-07-24 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b7d34f7a2c1"
down_revision: Union[str, Sequence[str], None] = "85f5756f3951"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("saham_fundamental", sa.Column("pbv", sa.Float(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("roe", sa.Float(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("roa", sa.Float(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("npm", sa.Float(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("eps", sa.Float(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("fs_date", sa.DateTime(), nullable=True))
    op.add_column("saham_fundamental", sa.Column("source_file", sa.String(length=255), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("saham_fundamental", "source_file")
    op.drop_column("saham_fundamental", "fs_date")
    op.drop_column("saham_fundamental", "eps")
    op.drop_column("saham_fundamental", "npm")
    op.drop_column("saham_fundamental", "roa")
    op.drop_column("saham_fundamental", "roe")
    op.drop_column("saham_fundamental", "pbv")
