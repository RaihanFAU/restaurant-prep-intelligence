from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import clear_session_cookie, get_current_user, set_session_cookie
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.repositories import worker_repository
from app.services.auth_service import authenticate, authenticate_pin
from app.services.errors import CSRFError, InactiveAccountError, InvalidCredentialsError, InvalidPinError, PinLockedError

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def _safe_next(path: str) -> str:
    """Only ever redirect somewhere inside this app. A `next` value an
    attacker fully controls (e.g. a login link mailed to a worker with
    `?next=https://evil.example`) must never be followed as-is — that's a
    classic open-redirect phishing setup."""
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return "/"


@router.get("/login")
def login_form(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if get_current_user(request, db) is not None:
        return RedirectResponse(url=_safe_next(next), status_code=303)

    return templates.TemplateResponse(
        request, "login.html", {"t": TEXTS, "next": _safe_next(next), "error": None}
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    next_path = _safe_next(next)
    try:
        verify_csrf(request, csrf_token)
    except CSRFError:
        return templates.TemplateResponse(
            request, "login.html", {"t": TEXTS, "next": next_path, "error": TEXTS["csrf_error"]}, status_code=400
        )

    try:
        worker = authenticate(db, email, password)
    except (InvalidCredentialsError, InactiveAccountError):
        return templates.TemplateResponse(
            request, "login.html", {"t": TEXTS, "next": next_path, "error": TEXTS["login_error"]}, status_code=401
        )

    response = RedirectResponse(url=next_path, status_code=303)
    set_session_cookie(response, worker.id)
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response


def _worker_login_page(request: Request, db: Session, next_path: str, error: str | None, status_code: int = 200):
    workers = worker_repository.list_active_worker_accounts(db)
    return templates.TemplateResponse(
        request,
        "worker_login.html",
        {"t": TEXTS, "next": next_path, "error": error, "workers": workers},
        status_code=status_code,
    )


@router.get("/worker-login")
def worker_login_form(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if get_current_user(request, db) is not None:
        return RedirectResponse(url=_safe_next(next), status_code=303)
    return _worker_login_page(request, db, _safe_next(next), error=None)


@router.post("/worker-login")
def worker_login_submit(
    request: Request,
    display_name: str = Form(...),
    pin: str = Form(...),
    next: str = Form("/"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    next_path = _safe_next(next)
    try:
        verify_csrf(request, csrf_token)
    except CSRFError:
        return _worker_login_page(request, db, next_path, TEXTS["csrf_error"], status_code=400)

    try:
        worker = authenticate_pin(db, display_name, pin)
    except PinLockedError:
        return _worker_login_page(request, db, next_path, TEXTS["pin_locked_error"], status_code=429)
    except (InvalidPinError, InactiveAccountError):
        return _worker_login_page(request, db, next_path, TEXTS["pin_login_error"], status_code=401)

    response = RedirectResponse(url=next_path, status_code=303)
    set_session_cookie(response, worker.id)
    return response
