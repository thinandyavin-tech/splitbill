"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
    )
    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id"), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id"), nullable=False, index=True),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("paid_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("split_type", sa.String(10), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "group_id", "idempotency_key", name="uq_expenses_group_idempotency_key"
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint("split_type IN ('equal', 'exact')", name="ck_expenses_split_type"),
    )
    op.create_table(
        "expense_shares",
        sa.Column("expense_id", sa.Integer, sa.ForeignKey("expenses.id"), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_expense_shares_amount"),
    )


def downgrade() -> None:
    op.drop_table("expense_shares")
    op.drop_table("expenses")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("users")
