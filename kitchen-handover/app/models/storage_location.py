from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prepared_product import PreparedProduct
    from app.models.product_location_history import ProductLocationHistory


class StorageLocation(Base):
    """A physical place a prepared product can be stored, e.g. 'Kühlhaus 1'."""

    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    current_products: Mapped[list["PreparedProduct"]] = relationship(back_populates="current_location")
    location_history_entries: Mapped[list["ProductLocationHistory"]] = relationship(back_populates="storage_location")

    def __repr__(self) -> str:
        return f"StorageLocation(id={self.id}, name={self.name!r})"
