from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Worker


def get_worker(db: Session, worker_id: int) -> Worker | None:
    return db.get(Worker, worker_id)


def list_active_workers(db: Session) -> list[Worker]:
    stmt = select(Worker).where(Worker.is_active.is_(True)).order_by(Worker.display_name)
    return list(db.scalars(stmt))


def get_by_display_name(db: Session, display_name: str) -> Worker | None:
    stmt = select(Worker).where(Worker.display_name == display_name)
    return db.scalars(stmt).first()


def get_or_create_by_display_name(db: Session, display_name: str) -> Worker:
    """Used by the no-auth 'pick your name' flow (STEP 6) — a worker typing
    a name that doesn't exist yet simply creates it. Not exposed as a way to
    guess/create arbitrary data elsewhere (spec's "don't auto-create unknown
    entities" principle applies to catalog data, not this tiny identity
    convenience)."""
    existing = get_by_display_name(db, display_name)
    if existing is not None:
        return existing
    worker = Worker(display_name=display_name)
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker
