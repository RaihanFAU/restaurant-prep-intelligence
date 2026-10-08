from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import prepared_product_repository, section_repository, station_repository
from app.services.errors import ProductNotFoundError, StationNotFoundError
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_user)):
    service = PreparationTaskService(db)
    stations = station_repository.list_active_stations(db)
    station_rows = [
        {
            "station": station,
            "active_count": len(service.get_station_tasks_today(station.id)),
            "tomorrow_count": len(service.get_station_tasks_tomorrow(station.id)),
        }
        for station in stations
    ]
    return templates.TemplateResponse(
        request,
        "home.html",
        {"t": TEXTS, "station_rows": station_rows, "current_user": current_user},
    )


@router.get("/stations/{station_id}")
def station_page(
    station_id: int, request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_user)
):
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)

    service = PreparationTaskService(db)
    items = service.get_station_tasks_today(station_id)
    tomorrow_items = service.get_station_tasks_tomorrow(station_id)

    sections = section_repository.list_sections_for_station(db, station_id)
    sections_with_products = [
        {"section": section, "products": prepared_product_repository.list_products_for_section(db, section.id)}
        for section in sections
    ]
    direct_products = prepared_product_repository.list_products_for_station(db, station_id)

    return templates.TemplateResponse(
        request,
        "station.html",
        {
            "t": TEXTS,
            "station": station,
            "station_id": station.id,
            "items": items,
            "tomorrow_items": tomorrow_items,
            "sections_with_products": sections_with_products,
            "direct_products": direct_products,
            "current_user": current_user,
        },
    )


@router.get("/products/{product_id}")
def product_page(
    product_id: int, request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_user)
):
    product = prepared_product_repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)

    # The persistent "already marked for tomorrow" state must come from
    # the database on every load — not just from a one-off success
    # message right after the button was clicked — so it survives a
    # reload, and shows up for a different worker opening the same page.
    service = PreparationTaskService(db)
    tomorrow_task = service.get_active_tomorrow_task(product_id)

    return templates.TemplateResponse(
        request,
        "product.html",
        {
            "t": TEXTS,
            "product": product,
            "current_user": current_user,
            "tomorrow_task": tomorrow_task,
            "status_message": TEXTS["already_marked_message"] if tomorrow_task else None,
        },
    )
