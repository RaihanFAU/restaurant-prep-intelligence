"""The MVP's session mechanism: a cryptographically signed, timestamped
cookie value (not a JWT — no third-party claims format, just an
HMAC-signed payload via itsdangerous, the same mechanism frameworks like
Flask use for their default session cookie). No server-side session table:
the signature + embedded issue time are enough to verify authenticity and
expiry on every request, and logout simply deletes the cookie.
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

_SALT = "kitchen-handover-session"

_serializer = URLSafeTimedSerializer(settings.session_secret_key, salt=_SALT)


def create_session_token(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def read_session_token(token: str) -> int | None:
    """Returns the user_id if the token is validly signed and not expired,
    else None. Never raises — a bad/forged/expired cookie is simply treated
    as "not logged in", same as no cookie at all."""
    try:
        data = _serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    user_id = data.get("user_id") if isinstance(data, dict) else None
    return user_id if isinstance(user_id, int) else None
