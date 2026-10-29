"""seed users and groups

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

USERS = [(1, "alice"), (2, "bob"), (3, "carol"), (4, "dan")]
GROUPS = [(1, "Chiang Mai trip"), (2, "Office lunch")]
MEMBERS = [(1, 1), (1, 2), (1, 3), (2, 2), (2, 4)]


def upgrade() -> None:
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("username", sa.String))
    groups = sa.table("groups", sa.column("id", sa.Integer), sa.column("name", sa.String))
    members = sa.table(
        "group_members", sa.column("group_id", sa.Integer), sa.column("user_id", sa.Integer)
    )
    op.bulk_insert(users, [{"id": i, "username": u} for i, u in USERS])
    op.bulk_insert(groups, [{"id": i, "name": n} for i, n in GROUPS])
    op.bulk_insert(members, [{"group_id": g, "user_id": u} for g, u in MEMBERS])
    # Explicit ids were inserted, so move the sequences past them.
    op.execute("SELECT setval('users_id_seq', (SELECT max(id) FROM users))")
    op.execute("SELECT setval('groups_id_seq', (SELECT max(id) FROM groups))")


def downgrade() -> None:
    op.execute("DELETE FROM group_members")
    op.execute("DELETE FROM groups")
    op.execute("DELETE FROM users")
