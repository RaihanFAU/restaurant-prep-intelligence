from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, hash_pin, verify_password, verify_pin
from app.models import Worker
from app.core.enums import Role
from app.repositories import worker_repository
from app.services.errors import InactiveAccountError, InvalidCredentialsError, InvalidPinError, PinLockedError

# A constant, pre-hashed dummy value checked when the email doesn't exist at
# all, so "unknown email" and "wrong password" take roughly the same amount
# of time — a real (if minor, for a kitchen app) email-enumeration mitigation,
# not security theater: it costs nothing and closes an easy timing probe.
_DUMMY_HASH = hash_password("not-a-real-password-used-only-for-timing-safety")

# Same idea, for the PIN login path.
_DUMMY_PIN_HASH = hash_pin("0000")


def authenticate(db: Session, email: str, password: str) -> Worker:
    worker = worker_repository.get_by_email(db, email)
    hash_to_check = worker.password_hash if worker is not None else _DUMMY_HASH
    password_ok = verify_password(password, hash_to_check)

    if worker is None or not password_ok:
        # Same error for "no such email" and "wrong password" — never let
        # login responses reveal which one it was.
        raise InvalidCredentialsError()

    if not worker.is_active:
        raise InactiveAccountError()

    return worker


def _pin_is_locked(worker: Worker) -> bool:
    return worker.pin_locked_until is not None and worker.pin_locked_until > datetime.utcnow()


def _record_failed_pin_attempt(db: Session, worker: Worker) -> None:
    worker.failed_pin_attempts += 1
    if worker.failed_pin_attempts >= settings.pin_max_failed_attempts:
        worker.pin_locked_until = datetime.utcnow() + timedelta(seconds=settings.pin_lockout_seconds)
    worker_repository.save(db, worker)


def _reset_pin_attempts(db: Session, worker: Worker) -> None:
    if worker.failed_pin_attempts or worker.pin_locked_until:
        worker.failed_pin_attempts = 0
        worker.pin_locked_until = None
        worker_repository.save(db, worker)


def authenticate_pin(db: Session, display_name: str, pin: str) -> Worker:
    """WORKER NAME + 4-digit PIN — the fast daily-use login. Never usable
    for an ADMIN account (ADMIN always needs email+password, enforced
    below), and locked out for a while after too many wrong PINs in a row
    (pin_max_failed_attempts / pin_lockout_seconds in config)."""
    worker = worker_repository.get_by_display_name(db, display_name)

    # Check the lock before even looking at the submitted PIN — a locked
    # account must reject every attempt, correct PIN or not.
    if worker is not None and _pin_is_locked(worker):
        raise PinLockedError()

    hash_to_check = worker.pin_hash if (worker is not None and worker.pin_hash) else _DUMMY_PIN_HASH
    pin_ok = verify_pin(pin, hash_to_check)
    is_valid_worker_account = worker is not None and worker.pin_hash is not None and worker.role == Role.WORKER

    if not is_valid_worker_account or not pin_ok:
        # Same error for "no such worker", "that account has no PIN",
        # "that's an ADMIN account", and "wrong PIN" — never reveal which.
        if worker is not None:
            _record_failed_pin_attempt(db, worker)
        raise InvalidPinError()

    if not worker.is_active:
        raise InactiveAccountError()

    _reset_pin_attempts(db, worker)
    return worker
