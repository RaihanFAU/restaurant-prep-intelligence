from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.csrf import verify_csrf
from app.core.enums import TaskPriority
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import prepared_product_repository
from app.services.errors import InactiveProductError, ProductNotFoundError
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/admin/tasks", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _render(request: Request, current_user: Worker, db: Session, error: str | None = None, status_code: int = 200):
    service = PreparationTaskService(db)
    tasks = service.list_all_tasks()
    products = prepared_product_repository.list_all_products(db)
    return templates.TemplateResponse(
        request,
        "admin/tasks.html",
        {
            "t": TEXTS,
            "current_user": current_user,
            "tasks": tasks,
            "products": [p for p in products if p.is_active],
            "today": date.today(),
            "error": error,
        },
        status_code=status_code,
    )


@router.get("")
def list_tasks(request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)):
    return _render(request, current_user, db)


@router.post("/{task_id}/priority")
def set_priority(
    task_id: int,
    request: Request,
    priority: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    PreparationTaskService(db).set_priority(task_id, TaskPriority(priority))
    return RedirectResponse(url="/admin/tasks", status_code=303)


@router.post("/{task_id}/pin")
def pin_task(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    PreparationTaskService(db).set_pinned(task_id, True)
    return RedirectResponse(url="/admin/tasks", status_code=303)


@router.post("/{task_id}/unpin")
def unpin_task(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    PreparationTaskService(db).set_pinned(task_id, False)
    return RedirectResponse(url="/admin/tasks", status_code=303)


@router.post("")
def create_manual_task(
    request: Request,
    product_id: int = Form(...),
    due_date: date = Form(...),
    priority: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        PreparationTaskService(db).create_manual_task(product_id, due_date, TaskPriority(priority), current_user.id)
    except (ProductNotFoundError, InactiveProductError) as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)
    return RedirectResponse(url="/admin/tasks", status_code=303)
