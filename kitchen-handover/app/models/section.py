from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prepared_product import PreparedProduct
    from app.models.station import Station


class Section(Base):
    """A sub-section of a station, e.g. PASS -> DIPS / SALAT / SCHWEIN.

    Not every station has sections (GRILL, FRITTEUSE, DESSERT currently
    don't) — a PreparedProduct may belong to a station directly, with
    section_id left null.
    """

    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("station_id", "name", name="uq_section_station_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    station: Mapped["Station"] = relationship(back_populates="sections")
    products: Mapped[list["PreparedProduct"]] = relationship(back_populates="section")

    def __repr__(self) -> str:
        return f"Section(id={self.id}, station_id={self.station_id}, name={self.name!r})"
