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
