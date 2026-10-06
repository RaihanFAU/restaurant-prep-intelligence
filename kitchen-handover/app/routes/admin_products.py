from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.repositories import prepared_product_repository, section_repository, station_repository
from app.services import catalog_admin_service
from app.services.errors import (
    ProductNotFoundError,
    SectionNotFoundError,
    SectionStationMismatchError,
    StationNotFoundError,
)

router = APIRouter(prefix="/admin/products", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_products(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    products = prepared_product_repository.list_all_products(db, search=q or None)
    stations = station_repository.list_all_stations(db)
    sections = section_repository.list_all_sections(db)
    return templates.TemplateResponse(
        request,
        "admin/products.html",
        {
            "t": TEXTS,
            "current_user": current_user,
            "products": products,
            "stations": stations,
            "sections": sections,
            "q": q,
            "error": None,
        },
    )


@router.post("")
def create_product(
    request: Request,
    name_de: str = Form(...),
    name_en: str = Form(""),
    station_id: int = Form(...),
    section_id: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.create_product(
            db,
            name_de=name_de.strip(),
            name_en=(name_en.strip() or None),
            station_id=station_id,
            section_id=(int(section_id) if section_id else None),
        )
    except (StationNotFoundError, SectionNotFoundError, SectionStationMismatchError) as exc:
        products = prepared_product_repository.list_all_products(db)
        stations = station_repository.list_all_stations(db)
        sections = section_repository.list_all_sections(db)
        return templates.TemplateResponse(
            request,
            "admin/products.html",
            {
                "t": TEXTS,
                "current_user": current_user,
                "products": products,
                "stations": stations,
                "sections": sections,
                "q": "",
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(url="/admin/products", status_code=303)


@router.get("/{product_id}/edit")
def edit_product_form(
    product_id: int, request: Request, db: Session = Depends(get_db), current_user: Worker = Depends(require_admin)
):
    product = prepared_product_repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    stations = station_repository.list_all_stations(db)
    sections = section_repository.list_all_sections(db)
    return templates.TemplateResponse(
        request,
        "admin/product_edit.html",
        {"t": TEXTS, "current_user": current_user, "product": product, "stations": stations, "sections": sections, "error": None},
    )


@router.post("/{product_id}/edit")
def edit_product_submit(
    product_id: int,
    request: Request,
    name_de: str = Form(...),
    name_en: str = Form(""),
    station_id: int = Form(...),
    section_id: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    try:
        catalog_admin_service.update_product(
            db,
            product_id,
            name_de=name_de.strip(),
            name_en=(name_en.strip() or None),
            station_id=station_id,
            section_id=(int(section_id) if section_id else None),
        )
    except (ProductNotFoundError, StationNotFoundError, SectionNotFoundError, SectionStationMismatchError) as exc:
        product = prepared_product_repository.get_product(db, product_id)
        stations = station_repository.list_all_stations(db)
        sections = section_repository.list_all_sections(db)
        return templates.TemplateResponse(
            request,
            "admin/product_edit.html",
            {
                "t": TEXTS,
                "current_user": current_user,
                "product": product,
                "stations": stations,
                "sections": sections,
                "error": str(exc),
            },
            status_code=400,
        )
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/{product_id}/activate")
def activate_product(
    product_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_product_active(db, product_id, True)
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/{product_id}/deactivate")
def deactivate_product(
    product_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_admin),
):
    verify_csrf(request, csrf_token)
    catalog_admin_service.set_product_active(db, product_id, False)
    return RedirectResponse(url="/admin/products", status_code=303)
