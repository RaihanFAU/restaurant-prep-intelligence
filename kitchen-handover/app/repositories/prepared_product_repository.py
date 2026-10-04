from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PreparedProduct


def get_product(db: Session, product_id: int) -> PreparedProduct | None:
    return db.get(PreparedProduct, product_id)


def list_products_for_station(db: Session, station_id: int) -> list[PreparedProduct]:
    """Products belonging directly to a station (section_id is null) — used
    for stations like GRILL that currently have no sub-sections."""
    stmt = (
        select(PreparedProduct)
        .where(
            PreparedProduct.station_id == station_id,
            PreparedProduct.section_id.is_(None),
            PreparedProduct.is_active.is_(True),
        )
        .order_by(PreparedProduct.name_de)
    )
    return list(db.scalars(stmt))


def list_products_for_section(db: Session, section_id: int) -> list[PreparedProduct]:
    stmt = (
        select(PreparedProduct)
        .where(PreparedProduct.section_id == section_id, PreparedProduct.is_active.is_(True))
        .order_by(PreparedProduct.name_de)
    )
    return list(db.scalars(stmt))
