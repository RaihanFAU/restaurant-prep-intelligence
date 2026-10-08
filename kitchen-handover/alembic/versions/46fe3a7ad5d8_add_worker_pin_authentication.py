"""add worker pin authentication

Revision ID: 46fe3a7ad5d8
Revises: 110227238ba2
Create Date: 2026-10-08 21:27:40.817793

Adds fast WORKER NAME + 4-digit PIN login as a daily-use alternative to
email+password. ADMIN accounts are untouched (still email+password).

Two things worth calling out:

1. workers.password_hash is loosened from NOT NULL to nullable. A WORKER
   account created through the new /admin/users PIN flow never gets a
   password at all (admin-only accounts keep using
   scripts/create_admin.py or promotion-with-a-password-reset for that),
   so the column can no longer be mandatory for every row. Existing rows
   already have a password_hash and are unaffected by loosening the
   constraint.

2. The downgrade only drops the new columns; it deliberately does NOT
   re-tighten password_hash back to NOT NULL, because by the time anyone
   downgrades, PIN-only WORKER rows with no password_hash may already
   exist, and re-adding that NOT NULL constraint would fail against them.
   Same "lossy, dev-rollback-only" spirit as the previous migration's
   downgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46fe3a7ad5d8'
down_revision: Union[str, None] = '110227238ba2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workers") as batch_op:
        batch_op.add_column(sa.Column("pin_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("failed_pin_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("pin_locked_until", sa.DateTime(), nullable=True))
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("workers") as batch_op:
        batch_op.drop_column("pin_locked_until")
        batch_op.drop_column("failed_pin_attempts")
        batch_op.drop_column("pin_hash")
