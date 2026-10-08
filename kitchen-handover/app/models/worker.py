from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.db.base import Base


class Worker(Base):
    """A kitchen worker / user account.

    Real authentication, added when the earlier free "pick any name"
    mechanism was replaced — that mechanism let anyone record actions
    under anyone else's name, which is exactly what real restaurant use
    cannot allow. Accounts are created by an ADMIN
    (app/services/user_admin_service.py), never via public
    self-registration.

    ADMIN accounts authenticate with email + Argon2 password hash.
    WORKER accounts authenticate with display_name + a 4-digit PIN
    (Argon2-hashed too) — faster for daily kitchen use than typing an
    email and password on every shift. A PIN can never grant ADMIN
    access (enforced in auth_service.authenticate_pin), and repeated
    wrong PINs temporarily lock the account (failed_pin_attempts /
    pin_locked_until).
    """

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Exactly one of password_hash / pin_hash is set in practice: ADMIN
    # accounts authenticate with email+password, WORKER accounts with
    # display_name+PIN (see auth_service.authenticate / authenticate_pin).
    # Both are nullable at the DB level because neither role needs the other.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False, length=20, create_constraint=True, name="ck_worker_role"),
        default=Role.WORKER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"Worker(id={self.id}, display_name={self.display_name!r}, role={self.role})"
