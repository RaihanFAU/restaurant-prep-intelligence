from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import section_repository, station_repository
from app.services import catalog_admin_service
from app.services.errors import DuplicateNameError, SectionNotFoundError, StationNotFoundError

router = APIRouter(prefix="/admin/sections", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _render(request: Request, current_user: Worker, db: Session, error: str | None = None, status_code: int = 200):
    sections = section_repository.list_all_sections(db)
    stations = station_repository.list_all_stations(db)
    return templates.TemplateResponse(
        request,
        "admin/sections.html",
        {"t": TEXTS, "current_user": current_user, "sections": sections, "stations": stations, "error": error},
        status_code=status_code,
    )


@router.get("")
def list_sections(request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)):
    return _render(request, current_user, db)


@router.post("")
def create_section(
    request: Request,
    station_id: int = Form(...),
    name: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.create_section(db, station_id, name.strip())
    except (DuplicateNameError, StationNotFoundError) as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)
    return RedirectResponse(url="/admin/sections", status_code=303)


@router.post("/{section_id}/rename")
def rename_section(
    section_id: int,
    request: Request,
    name: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.rename_section(db, section_id, name.strip())
    except (DuplicateNameError, SectionNotFoundError) as exc:
        return _render(request, current_user, db, error=str(exc), status_code=400)
    return RedirectResponse(url="/admin/sections", status_code=303)


@router.post("/{section_id}/activate")
def activate_section(
    section_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_section_active(db, section_id, True)
    return RedirectResponse(url="/admin/sections", status_code=303)


@router.post("/{section_id}/deactivate")
def deactivate_section(
    section_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_section_active(db, section_id, False)
    return RedirectResponse(url="/admin/sections", status_code=303)
