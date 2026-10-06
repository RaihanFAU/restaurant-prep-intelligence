from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.db.base import Base


class Worker(Base):
    """A kitchen worker / user account.

    Real authentication (email + Argon2 password hash), added when the
    earlier free "pick any name" mechanism was replaced — that mechanism
    let anyone record actions under anyone else's name, which is exactly
    what real restaurant use cannot allow. Accounts are created by an
    ADMIN (app/services/user_admin_service.py), never via public
    self-registration.
    """

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
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
