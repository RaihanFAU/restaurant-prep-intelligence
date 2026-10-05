"""The MVP's entire 'auth' story: a cookie remembering which Worker row you
last picked on the /worker/select page. No passwords, no sessions table —
just enough to attribute actions to a name (spec STEP 6)."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import Worker
from app.repositories import worker_repository

WORKER_COOKIE_NAME = "worker_id"


def get_current_worker(request: Request, db: Session) -> Worker | None:
    raw = request.cookies.get(WORKER_COOKIE_NAME)
    if raw is None or not raw.isdigit():
        return None
    worker = worker_repository.get_worker(db, int(raw))
    if worker is None or not worker.is_active:
        return None
    return worker
