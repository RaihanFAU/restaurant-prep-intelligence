"""Admin-only catalog management: stations, sections, prepared products.
Prefers deactivation over deletion everywhere — historical PreparationTask
rows must stay valid, so nothing here ever hard-deletes a row another table
might reference.
"""

from sqlalchemy.orm import Session

from app.models import PreparedProduct, Section, Station
from app.repositories import prepared_product_repository, section_repository, station_repository
from app.services.errors import (
    DuplicateNameError,
    ProductNotFoundError,
    SectionNotFoundError,
    SectionStationMismatchError,
    StationNotFoundError,
)

# --- stations ---


def create_station(db: Session, name: str) -> Station:
    if station_repository.get_by_name(db, name) is not None:
        raise DuplicateNameError("station", name)
    return station_repository.create_station(db, name=name)


def rename_station(db: Session, station_id: int, new_name: str) -> Station:
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)
    clash = station_repository.get_by_name(db, new_name)
    if clash is not None and clash.id != station_id:
        raise DuplicateNameError("station", new_name)
    station.name = new_name
    return station_repository.save(db, station)


def set_station_active(db: Session, station_id: int, is_active: bool) -> Station:
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)
    station.is_active = is_active
    return station_repository.save(db, station)


# --- sections ---


def create_section(db: Session, station_id: int, name: str) -> Section:
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)
    if section_repository.get_by_station_and_name(db, station_id, name) is not None:
        raise DuplicateNameError("section", name)
    return section_repository.create_section(db, station_id=station_id, name=name)


def rename_section(db: Session, section_id: int, new_name: str) -> Section:
    section = section_repository.get_section(db, section_id)
    if section is None:
        raise SectionNotFoundError(section_id)
    clash = section_repository.get_by_station_and_name(db, section.station_id, new_name)
    if clash is not None and clash.id != section_id:
        raise DuplicateNameError("section", new_name)
    section.name = new_name
    return section_repository.save(db, section)


def set_section_active(db: Session, section_id: int, is_active: bool) -> Section:
    section = section_repository.get_section(db, section_id)
    if section is None:
        raise SectionNotFoundError(section_id)
    section.is_active = is_active
    return section_repository.save(db, section)


# --- products ---


def _validate_station_section_pair(db: Session, station_id: int, section_id: int | None) -> None:
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)
    if section_id is not None:
        section = section_repository.get_section(db, section_id)
        if section is None:
            raise SectionNotFoundError(section_id)
        if section.station_id != station_id:
            raise SectionStationMismatchError(section_id, station_id)


def create_product(
    db: Session, *, name_de: str, name_en: str | None, station_id: int, section_id: int | None
) -> PreparedProduct:
    _validate_station_section_pair(db, station_id, section_id)
    return prepared_product_repository.create_product(
        db, name_de=name_de, name_en=name_en, station_id=station_id, section_id=section_id
    )


def update_product(
    db: Session,
    product_id: int,
    *,
    name_de: str,
    name_en: str | None,
    station_id: int,
    section_id: int | None,
) -> PreparedProduct:
    product = prepared_product_repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    _validate_station_section_pair(db, station_id, section_id)
    product.name_de = name_de
    product.name_en = name_en
    product.station_id = station_id
    product.section_id = section_id
    return prepared_product_repository.save(db, product)


def set_product_active(db: Session, product_id: int, is_active: bool) -> PreparedProduct:
    product = prepared_product_repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    product.is_active = is_active
    return prepared_product_repository.save(db, product)
