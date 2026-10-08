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


# Worker PINs are hashed with the exact same Argon2 infrastructure as
# passwords — a PIN is just a short password, so there's no reason to build
# or depend on a second hashing scheme. Separate names only for readability
# at call sites (hash_pin/verify_pin vs hash_password/verify_password).
def hash_pin(raw_pin: str) -> str:
    return hash_password(raw_pin)


def verify_pin(raw_pin: str, pin_hash: str) -> bool:
    return verify_password(raw_pin, pin_hash)
