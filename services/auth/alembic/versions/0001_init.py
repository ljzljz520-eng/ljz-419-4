"""init: roles + users, seed roles and admin account

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

from app.security import hash_password

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ROLES = ["admin", "agent", "customer"]


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
    op.bulk_insert(roles, [{"id": i + 1, "name": name} for i, name in enumerate(ROLES)])

    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("username", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role_id", sa.Integer),
    )
    op.bulk_insert(users, [{
        "id": 1,
        "username": "admin",
        "password_hash": hash_password("admin123"),
        "role_id": 1,
    }])


def downgrade():
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
