"""Admin-only account management. Role enforcement itself happens at the
route layer (app/core/auth.require_admin) — this service assumes the
caller is already authorized and focuses on the actual business rules:
unique emails, hashed passwords, and never letting the last admin lock
everyone out.
"""

import re

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import hash_password, hash_pin
from app.models import Worker
from app.repositories import worker_repository
from app.services.errors import (
    DuplicateEmailError,
    DuplicateNameError,
    InvalidPinFormatError,
    LastAdminError,
    PasswordRequiredForAdminError,
    PinMismatchError,
    WorkerNotFoundError,
)

_PIN_PATTERN = re.compile(r"^\d{4}$")


def _validate_pin(pin: str, confirm_pin: str) -> None:
    if not _PIN_PATTERN.match(pin):
        raise InvalidPinFormatError()
    if pin != confirm_pin:
        raise PinMismatchError()


def create_user(db: Session, *, display_name: str, email: str, password: str, role: Role) -> Worker:
    """Creates an account with email+password — used for ADMIN accounts
    (scripts/create_admin.py; there is no UI form for this, see
    create_worker_pin for the everyday worker-creation flow)."""
    if worker_repository.get_by_email(db, email) is not None:
        raise DuplicateEmailError(email)
    return worker_repository.create_worker(
        db, display_name=display_name, email=email, password_hash=hash_password(password), role=role
    )


def create_worker_pin(
    db: Session, *, display_name: str, email: str, pin: str, confirm_pin: str, role: Role = Role.WORKER
) -> Worker:
    """The /admin/users creation form: a WORKER account with a 4-digit PIN
    instead of a password — the fast, daily-use login. Deliberately
    refuses to create an ADMIN this way: an ADMIN account with no password
    could never log in (ADMIN always authenticates with email+password)."""
    if role != Role.WORKER:
        raise PasswordRequiredForAdminError()
    _validate_pin(pin, confirm_pin)
    if worker_repository.get_by_email(db, email) is not None:
        raise DuplicateEmailError(email)
    if worker_repository.get_by_display_name(db, display_name) is not None:
        raise DuplicateNameError("worker", display_name)
    return worker_repository.create_worker(
        db, display_name=display_name, email=email, role=Role.WORKER, pin_hash=hash_pin(pin)
    )


def reset_pin(db: Session, worker_id: int, new_pin: str, confirm_pin: str) -> Worker:
    _validate_pin(new_pin, confirm_pin)
    worker = _get_or_raise(db, worker_id)
    worker.pin_hash = hash_pin(new_pin)
    # A PIN reset is also the recovery path for a lockout — an admin
    # resetting it is a deliberate, authenticated action, so clear it.
    worker.failed_pin_attempts = 0
    worker.pin_locked_until = None
    return worker_repository.save(db, worker)


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
    if new_role == Role.ADMIN and worker.password_hash is None:
        # This worker was created through the PIN-only flow and has never
        # had a password — promoting them now would create an ADMIN
        # account that can never log in.
        raise PasswordRequiredForAdminError()
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
