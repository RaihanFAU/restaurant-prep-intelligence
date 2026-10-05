from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import WORKER_COOKIE_NAME
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.repositories import worker_repository

router = APIRouter(prefix="/worker", tags=["worker"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/select")
def select_worker_form(request: Request, next: str = "/", db: Session = Depends(get_db)):
    workers = worker_repository.list_active_workers(db)
    return templates.TemplateResponse(
        request,
        "worker_select.html",
        {"t": TEXTS, "workers": workers, "next": next},
    )


@router.post("/select")
def select_worker(
    request: Request,
    next: str = Form("/"),
    worker_id: str = Form(""),
    new_name: str = Form(""),
    db: Session = Depends(get_db),
):
    new_name = new_name.strip()
    if new_name:
        worker = worker_repository.get_or_create_by_display_name(db, new_name)
    elif worker_id.isdigit():
        worker = worker_repository.get_worker(db, int(worker_id))
    else:
        worker = None

    response = RedirectResponse(url=next or "/", status_code=303)
    if worker is not None:
        response.set_cookie(WORKER_COOKIE_NAME, str(worker.id), max_age=60 * 60 * 24 * 30)
    return response
