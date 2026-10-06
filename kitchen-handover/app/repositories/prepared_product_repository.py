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


def list_all_products(db: Session, search: str | None = None) -> list[PreparedProduct]:
    """Admin view — every product including deactivated ones, optionally
    filtered by a case-insensitive substring match on either name."""
    stmt = select(PreparedProduct)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            PreparedProduct.name_de.ilike(like) | PreparedProduct.name_en.ilike(like)
        )
    stmt = stmt.order_by(PreparedProduct.name_de)
    return list(db.scalars(stmt))


def create_product(
    db: Session, *, name_de: str, name_en: str | None, station_id: int, section_id: int | None
) -> PreparedProduct:
    product = PreparedProduct(name_de=name_de, name_en=name_en, station_id=station_id, section_id=section_id)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def save(db: Session, product: PreparedProduct) -> PreparedProduct:
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
