"""add auth fields to worker and priority to preparation task

Revision ID: 110227238ba2
Revises: 272504d65f4b
Create Date: 2026-10-06 13:45:32.094740

Hand-adjusted after autogenerate. Autogenerate proposed adding
workers.email/password_hash/role directly as NOT NULL, which cannot
succeed against the existing demo rows ("Michael", "Anna") seeded under
the old no-auth workflow — SQLite (and any DB) rejects a NOT NULL column
with no default on a non-empty table.

This migration instead:
  1. adds the new Worker columns as nullable first,
  2. deletes the pre-auth demo accounts (they have no email/password and
     cannot satisfy the new schema — they only existed to support the free
     "pick any name" mechanism this change removes),
  3. THEN tightens email/password_hash to NOT NULL + unique.

This is the one unavoidable dev-data change called out in the task: it is
safe only because step 2 fails loudly (FK violation) instead of silently
corrupting history if any PreparationTask ever referenced those demo
workers. In this project's dev database it does not (verified before
writing this migration).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '110227238ba2'
down_revision: Union[str, None] = '272504d65f4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- PreparationTask: priority + pinning ---
    # server_default matches the Python-side default so any existing rows
    # (none in dev today, but this must still be correct in general) land
    # on the same values the model would have given them.
    with op.batch_alter_table("preparation_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.Enum("NORMAL", "HIGH", "URGENT", name="ck_task_priority", native_enum=False, length=20),
                nullable=False,
                server_default="URGENT",
            )
        )
        batch_op.add_column(
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        # batch_alter_table's add_column does NOT auto-emit the CHECK that
        # Enum(create_constraint=True) produces on a fresh CREATE TABLE
        # (verified: Base.metadata.create_all() gets it, this ALTER path
        # does not) — added explicitly so a migrated DB matches a freshly
        # created one.
        batch_op.create_check_constraint("ck_task_priority", "priority IN ('NORMAL', 'HIGH', 'URGENT')")

    # --- Worker: add auth columns as nullable first ---
    with op.batch_alter_table("workers") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "role",
                sa.Enum("ADMIN", "WORKER", name="ck_worker_role", native_enum=False, length=20),
                nullable=False,
                server_default="WORKER",
            )
        )
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
        )

    # --- remove pre-auth demo accounts (see module docstring) ---
    op.execute("DELETE FROM workers WHERE email IS NULL")

    # --- now that the table holds only real accounts, tighten the constraints ---
    with op.batch_alter_table("workers") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
        batch_op.create_unique_constraint("uq_workers_email", ["email"])
        batch_op.create_check_constraint("ck_worker_role", "role IN ('ADMIN', 'WORKER')")


def downgrade() -> None:
    # Lossy: real accounts created after this migration lose their
    # email/password/role on downgrade. Acceptable for an MVP rollback path,
    # not meant as a production undo once real accounts are in use.
    with op.batch_alter_table("workers") as batch_op:
        batch_op.drop_constraint("ck_worker_role", type_="check")
        batch_op.drop_constraint("uq_workers_email", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("role")
        batch_op.drop_column("password_hash")
        batch_op.drop_column("email")

    with op.batch_alter_table("preparation_tasks") as batch_op:
        batch_op.drop_constraint("ck_task_priority", type_="check")
        batch_op.drop_column("is_pinned")
        batch_op.drop_column("priority")
