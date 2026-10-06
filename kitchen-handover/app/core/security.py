"""Password hashing — Argon2 (OWASP's current recommendation), via
argon2-cffi directly rather than passlib (passlib is effectively
unmaintained and has had friction with newer bcrypt releases).

Never log or print a raw password or a hash in a way that could leak it —
callers must not pass these to logging statements.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, raw_password)
    except VerifyMismatchError:
        return False
