from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Worker(Base):
    """A kitchen worker. No authentication in the MVP — a worker just picks
    or types their display name, so actions (prepare-tomorrow, location
    change, task completion) can record who did them.
    """

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"Worker(id={self.id}, display_name={self.display_name!r})"
