"""Authentication dependencies for routes. This is the one place that turns
a request's cookie into "the current logged-in Worker" — every
operational route must get its user from here, never from a client-supplied
ID (spec: "do not allow the client to submit created_by/completed_by and
trust it").
"""

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Role
from app.core.session import create_session_token, read_session_token
from app.db.session import get_db
from app.models import Worker
from app.repositories import worker_repository
from app.services.errors import ForbiddenError, LoginRequiredError

SESSION_COOKIE_NAME = "session"


def set_session_cookie(response: Response, worker_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(worker_id),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Worker | None:
    """Returns the logged-in Worker, or None — never raises. Use `require_user`
    / `require_admin` in routes that must reject anonymous access; this
    bare version exists only for the rare page that wants to render
    differently when logged in vs not (none currently do, but e.g. /login
    itself checks this to bounce an already-logged-in user straight through)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        return None
    worker_id = read_session_token(token)
    if worker_id is None:
        return None
    worker = worker_repository.get_worker(db, worker_id)
    if worker is None or not worker.is_active:
        return None
    return worker


def require_user(request: Request, db: Session = Depends(get_db)) -> Worker:
    user = get_current_user(request, db)
    if user is None:
        raise LoginRequiredError(next_path=request.url.path)
    return user


def require_admin(user: Worker = Depends(require_user)) -> Worker:
    if user.role != Role.ADMIN:
        raise ForbiddenError()
    return user
