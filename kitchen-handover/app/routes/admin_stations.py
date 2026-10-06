from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import station_repository
from app.services import catalog_admin_service
from app.services.errors import DuplicateNameError, StationNotFoundError

router = APIRouter(prefix="/admin/stations", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_stations(request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)):
    stations = station_repository.list_all_stations(db)
    return templates.TemplateResponse(
        request, "admin/stations.html", {"t": TEXTS, "current_user": current_user, "stations": stations, "error": None}
    )


@router.post("")
def create_station(
    request: Request,
    name: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.create_station(db, name.strip())
    except DuplicateNameError as exc:
        stations = station_repository.list_all_stations(db)
        return templates.TemplateResponse(
            request,
            "admin/stations.html",
            {"t": TEXTS, "current_user": current_user, "stations": stations, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url="/admin/stations", status_code=303)


@router.post("/{station_id}/rename")
def rename_station(
    station_id: int,
    request: Request,
    name: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.rename_station(db, station_id, name.strip())
    except (DuplicateNameError, StationNotFoundError) as exc:
        stations = station_repository.list_all_stations(db)
        return templates.TemplateResponse(
            request,
            "admin/stations.html",
            {"t": TEXTS, "current_user": current_user, "stations": stations, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse(url="/admin/stations", status_code=303)


@router.post("/{station_id}/activate")
def activate_station(
    station_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_station_active(db, station_id, True)
    return RedirectResponse(url="/admin/stations", status_code=303)


@router.post("/{station_id}/deactivate")
def deactivate_station(
    station_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_station_active(db, station_id, False)
    return RedirectResponse(url="/admin/stations", status_code=303)
