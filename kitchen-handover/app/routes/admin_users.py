from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.csrf import verify_csrf
from app.core.enums import Role
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import worker_repository
from app.services import user_admin_service
from app.services.errors import DuplicateEmailError, LastAdminError, WorkerNotFoundError

router = APIRouter(prefix="/admin/users", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_users(request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)):
    workers = worker_repository.list_all_workers(db)
    return templates.TemplateResponse(
        request, "admin/users.html", {"t": TEXTS, "current_user": current_user, "workers": workers, "error": None}
    )


@router.post("")
def create_user(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("WORKER"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        user_admin_service.create_user(
            db, display_name=display_name.strip(), email=email.strip().lower(), password=password, role=Role(role)
        )
    except DuplicateEmailError as exc:
        workers = worker_repository.list_all_workers(db)
        return templates.TemplateResponse(
            request,
            "admin/users.html",
            {"t": TEXTS, "current_user": current_user, "workers": workers, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/{worker_id}/edit")
def edit_user_form(
    worker_id: int, request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)
):
    worker = worker_repository.get_worker(db, worker_id)
    if worker is None:
        raise WorkerNotFoundError(worker_id)
    return templates.TemplateResponse(
        request, "admin/user_edit.html", {"t": TEXTS, "current_user": current_user, "worker": worker, "error": None}
    )


@router.post("/{worker_id}/role")
def change_role(
    worker_id: int,
    request: Request,
    role: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        user_admin_service.change_role(db, worker_id, Role(role))
    except LastAdminError as exc:
        worker = worker_repository.get_worker(db, worker_id)
        return templates.TemplateResponse(
            request,
            "admin/user_edit.html",
            {"t": TEXTS, "current_user": current_user, "worker": worker, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url=f"/admin/users/{worker_id}/edit", status_code=303)


@router.post("/{worker_id}/activate")
def activate_user(
    worker_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    user_admin_service.set_active(db, worker_id, True)
    return RedirectResponse(url=f"/admin/users/{worker_id}/edit", status_code=303)


@router.post("/{worker_id}/deactivate")
def deactivate_user(
    worker_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        user_admin_service.set_active(db, worker_id, False)
    except LastAdminError as exc:
        worker = worker_repository.get_worker(db, worker_id)
        return templates.TemplateResponse(
            request,
            "admin/user_edit.html",
            {"t": TEXTS, "current_user": current_user, "worker": worker, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url=f"/admin/users/{worker_id}/edit", status_code=303)


@router.post("/{worker_id}/password")
def reset_password(
    worker_id: int,
    request: Request,
    new_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    user_admin_service.set_password(db, worker_id, new_password)
    return RedirectResponse(url=f"/admin/users/{worker_id}/edit", status_code=303)
