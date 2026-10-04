from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.preparation_task import PreparationTask
    from app.models.product_location_history import ProductLocationHistory
    from app.models.section import Section
    from app.models.station import Station
    from app.models.storage_location import StorageLocation


class PreparedProduct(Base):
    """A prepared product / mise-en-place item — e.g. Krautsalat, Remoulade.

    This is NOT a raw ingredient (see docs/mvp/kitchen-handover.md §1/§21 of
    the original prompt). name_de is the primary MVP display name; name_en
    is optional and filled in as translations are confirmed.
    """

    __tablename__ = "prepared_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_de: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id"), nullable=True)
    current_location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("storage_locations.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    station: Mapped["Station"] = relationship(back_populates="products")
    section: Mapped[Optional["Section"]] = relationship(back_populates="products")
    current_location: Mapped[Optional["StorageLocation"]] = relationship(back_populates="current_products")

    tasks: Mapped[list["PreparationTask"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    location_history: Mapped[list["ProductLocationHistory"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        # id as a tiebreaker: SQLite's CURRENT_TIMESTAMP has only
        # second-level resolution, so two changes within the same second
        # would otherwise sort ambiguously.
        order_by="(ProductLocationHistory.recorded_at.desc(), ProductLocationHistory.id.desc())",
    )

    def __repr__(self) -> str:
        return f"PreparedProduct(id={self.id}, name_de={self.name_de!r})"
