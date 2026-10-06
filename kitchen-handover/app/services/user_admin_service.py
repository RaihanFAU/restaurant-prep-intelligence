"""Admin-only account management. Role enforcement itself happens at the
route layer (app/core/auth.require_admin) — this service assumes the
caller is already authorized and focuses on the actual business rules:
unique emails, hashed passwords, and never letting the last admin lock
everyone out.
"""

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import hash_password
from app.models import Worker
from app.repositories import worker_repository
from app.services.errors import DuplicateEmailError, LastAdminError, WorkerNotFoundError


def create_user(db: Session, *, display_name: str, email: str, password: str, role: Role) -> Worker:
    if worker_repository.get_by_email(db, email) is not None:
        raise DuplicateEmailError(email)
    return worker_repository.create_worker(
        db, display_name=display_name, email=email, password_hash=hash_password(password), role=role
    )


def _get_or_raise(db: Session, worker_id: int) -> Worker:
    worker = worker_repository.get_worker(db, worker_id)
    if worker is None:
        raise WorkerNotFoundError(worker_id)
    return worker


def change_role(db: Session, worker_id: int, new_role: Role) -> Worker:
    worker = _get_or_raise(db, worker_id)
    if worker.role == Role.ADMIN and new_role != Role.ADMIN:
        if worker_repository.count_active_admins(db, exclude_worker_id=worker.id) == 0:
            raise LastAdminError()
    worker.role = new_role
    return worker_repository.save(db, worker)


def set_active(db: Session, worker_id: int, is_active: bool) -> Worker:
    worker = _get_or_raise(db, worker_id)
    if not is_active and worker.role == Role.ADMIN:
        if worker_repository.count_active_admins(db, exclude_worker_id=worker.id) == 0:
            raise LastAdminError()
    worker.is_active = is_active
    return worker_repository.save(db, worker)


def set_password(db: Session, worker_id: int, new_password: str) -> Worker:
    worker = _get_or_raise(db, worker_id)
    worker.password_hash = hash_password(new_password)
    return worker_repository.save(db, worker)
