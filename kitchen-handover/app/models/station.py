from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prepared_product import PreparedProduct
    from app.models.section import Section


class Station(Base):
    """A kitchen station, e.g. PASS, GRILL, FRITTEUSE, DESSERT.

    Names are editable restaurant data, never hardcoded into application
    logic (see docs/mvp/kitchen-handover.md §1).
    """

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sections: Mapped[list["Section"]] = relationship(back_populates="station")
    products: Mapped[list["PreparedProduct"]] = relationship(back_populates="station")

    def __repr__(self) -> str:
        return f"Station(id={self.id}, name={self.name!r})"
