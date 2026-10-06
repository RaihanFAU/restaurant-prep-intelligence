from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models import Worker


def get_worker(db: Session, worker_id: int) -> Worker | None:
    return db.get(Worker, worker_id)


def get_by_email(db: Session, email: str) -> Worker | None:
    stmt = select(Worker).where(Worker.email == email)
    return db.scalars(stmt).first()


def list_active_workers(db: Session) -> list[Worker]:
    stmt = select(Worker).where(Worker.is_active.is_(True)).order_by(Worker.display_name)
    return list(db.scalars(stmt))


def list_all_workers(db: Session) -> list[Worker]:
    """Admin view — includes deactivated accounts too."""
    stmt = select(Worker).order_by(Worker.display_name)
    return list(db.scalars(stmt))


def count_active_admins(db: Session, exclude_worker_id: int | None = None) -> int:
    stmt = select(Worker).where(Worker.role == Role.ADMIN, Worker.is_active.is_(True))
    if exclude_worker_id is not None:
        stmt = stmt.where(Worker.id != exclude_worker_id)
    return len(list(db.scalars(stmt)))


def create_worker(
    db: Session, *, display_name: str, email: str, password_hash: str, role: Role
) -> Worker:
    worker = Worker(display_name=display_name, email=email, password_hash=password_hash, role=role)
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def save(db: Session, worker: Worker) -> Worker:
    """Persist in-place edits to an already-loaded Worker (role/active/etc)."""
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker
