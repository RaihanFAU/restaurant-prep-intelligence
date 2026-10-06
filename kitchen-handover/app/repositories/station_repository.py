from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Station


def get_station(db: Session, station_id: int) -> Station | None:
    return db.get(Station, station_id)


def list_active_stations(db: Session) -> list[Station]:
    stmt = select(Station).where(Station.is_active.is_(True)).order_by(Station.id)
    return list(db.scalars(stmt))


def list_all_stations(db: Session) -> list[Station]:
    """Admin view — includes deactivated stations too."""
    stmt = select(Station).order_by(Station.name)
    return list(db.scalars(stmt))


def get_by_name(db: Session, name: str) -> Station | None:
    stmt = select(Station).where(Station.name == name)
    return db.scalars(stmt).first()


def create_station(db: Session, *, name: str) -> Station:
    station = Station(name=name)
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


def save(db: Session, station: Station) -> Station:
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
