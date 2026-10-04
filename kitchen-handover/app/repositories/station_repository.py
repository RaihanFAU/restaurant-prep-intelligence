from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Station


def get_station(db: Session, station_id: int) -> Station | None:
    return db.get(Station, station_id)


def list_active_stations(db: Session) -> list[Station]:
    stmt = select(Station).where(Station.is_active.is_(True)).order_by(Station.id)
    return list(db.scalars(stmt))
