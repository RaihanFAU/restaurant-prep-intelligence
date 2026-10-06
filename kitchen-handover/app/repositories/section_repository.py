from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Section


def get_section(db: Session, section_id: int) -> Section | None:
    return db.get(Section, section_id)


def list_sections_for_station(db: Session, station_id: int) -> list[Section]:
    stmt = (
        select(Section)
        .where(Section.station_id == station_id, Section.is_active.is_(True))
        .order_by(Section.name)
    )
    return list(db.scalars(stmt))


def list_all_sections(db: Session) -> list[Section]:
    """Admin view — every section, every station, including deactivated ones."""
    stmt = select(Section).order_by(Section.station_id, Section.name)
    return list(db.scalars(stmt))


def get_by_station_and_name(db: Session, station_id: int, name: str) -> Section | None:
    stmt = select(Section).where(Section.station_id == station_id, Section.name == name)
    return db.scalars(stmt).first()


def create_section(db: Session, *, station_id: int, name: str) -> Section:
    section = Section(station_id=station_id, name=name)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def save(db: Session, section: Section) -> Section:
    db.add(section)
    db.commit()
    db.refresh(section)
    return section
