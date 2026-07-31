"""add broker summary

Revision ID: 2f5b4c8d9a10
Revises: 8cb465f0f5a6
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f5b4c8d9a10"
down_revision: Union[str, Sequence[str], None] = "8cb465f0f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broker_summary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("summary_date", sa.DateTime(), nullable=False),
        sa.Column("top3_buy_val", sa.Float(), nullable=False),
        sa.Column("top3_sell_val", sa.Float(), nullable=False),
        sa.Column("net_foreign_val", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_buy_val", sa.Float(), nullable=True),
        sa.Column("total_sell_val", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("source_file", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_broker_summary_ticker_date", "broker_summary", ["ticker", "summary_date"])


def downgrade() -> None:
    op.drop_index("idx_broker_summary_ticker_date", table_name="broker_summary")
    op.drop_table("broker_summary")
