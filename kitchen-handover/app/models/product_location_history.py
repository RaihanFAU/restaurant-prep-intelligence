from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prepared_product import PreparedProduct
    from app.models.storage_location import StorageLocation
    from app.models.worker import Worker


class ProductLocationHistory(Base):
    """An append-only record of 'this product was stored here at this time'.

    Whenever a product's current location changes, the service layer must:
      1. update PreparedProduct.current_location_id, and
      2. insert one of these rows,
    inside a single transaction (docs/mvp/kitchen-handover.md §24/§11 of the
    original prompt). This table is never updated or deleted — it's the
    simple movement history, not a full warehouse audit system.
    """

    __tablename__ = "product_location_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    prepared_product_id: Mapped[int] = mapped_column(ForeignKey("prepared_products.id"), nullable=False)
    storage_location_id: Mapped[int] = mapped_column(ForeignKey("storage_locations.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False)

    product: Mapped["PreparedProduct"] = relationship(back_populates="location_history")
    storage_location: Mapped["StorageLocation"] = relationship(back_populates="location_history_entries")
    recorded_by: Mapped["Worker"] = relationship()

    def __repr__(self) -> str:
        return (
            f"ProductLocationHistory(id={self.id}, product_id={self.prepared_product_id}, "
            f"location_id={self.storage_location_id}, recorded_at={self.recorded_at})"
        )
