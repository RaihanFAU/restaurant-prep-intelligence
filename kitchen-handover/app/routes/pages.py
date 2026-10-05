from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import get_current_worker
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.repositories import prepared_product_repository, section_repository, station_repository
from app.services.errors import ProductNotFoundError, StationNotFoundError
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    service = PreparationTaskService(db)
    stations = station_repository.list_active_stations(db)
    station_rows = [
        {"station": station, "active_count": len(service.get_station_tasks_today(station.id))}
        for station in stations
    ]
    worker = get_current_worker(request, db)
    return templates.TemplateResponse(
        request,
        "home.html",
        {"t": TEXTS, "station_rows": station_rows, "worker": worker},
    )


@router.get("/stations/{station_id}")
def station_page(station_id: int, request: Request, db: Session = Depends(get_db)):
    station = station_repository.get_station(db, station_id)
    if station is None:
        raise StationNotFoundError(station_id)

    service = PreparationTaskService(db)
    items = service.get_station_tasks_today(station_id)

    sections = section_repository.list_sections_for_station(db, station_id)
    sections_with_products = [
        {"section": section, "products": prepared_product_repository.list_products_for_section(db, section.id)}
        for section in sections
    ]
    direct_products = prepared_product_repository.list_products_for_station(db, station_id)

    worker = get_current_worker(request, db)
    return templates.TemplateResponse(
        request,
        "station.html",
        {
            "t": TEXTS,
            "station": station,
            "station_id": station.id,
            "items": items,
            "sections_with_products": sections_with_products,
            "direct_products": direct_products,
            "worker": worker,
        },
    )


@router.get("/products/{product_id}")
def product_page(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = prepared_product_repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)

    worker = get_current_worker(request, db)
    return templates.TemplateResponse(
        request,
        "product.html",
        {"t": TEXTS, "product": product, "worker": worker},
    )
