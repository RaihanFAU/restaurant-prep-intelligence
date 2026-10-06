from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Worker
from app.repositories import worker_repository
from app.services.errors import InactiveAccountError, InvalidCredentialsError

# A constant, pre-hashed dummy value checked when the email doesn't exist at
# all, so "unknown email" and "wrong password" take roughly the same amount
# of time — a real (if minor, for a kitchen app) email-enumeration mitigation,
# not security theater: it costs nothing and closes an easy timing probe.
_DUMMY_HASH = hash_password("not-a-real-password-used-only-for-timing-safety")


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
