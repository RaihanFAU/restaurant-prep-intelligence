from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.i18n import TEXTS
from app.db.session import get_db
from app.schemas.preparation_task import PrepareTomorrowResponse, TaskOut
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/{product_id}/prepare-tomorrow")
def prepare_tomorrow(product_id: int, worker_id: int, request: Request, db: Session = Depends(get_db)):
    """worker_id is a query parameter, not a JSON body — this keeps the
    same endpoint trivially callable both from an HTMX form (worker_id
    baked into the posted URL, see product.html) and from tests/API
    clients (`client.post(url, params={"worker_id": ...})`), with no
    content-type branching needed."""
    service = PreparationTaskService(db)
    result = service.prepare_tomorrow(product_id, worker_id)

    message = TEXTS["already_marked_message"] if result.already_marked else TEXTS["prepared_tomorrow_message"]

    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(
            request,
            "_prepare_tomorrow_feedback.html",
            {"t": TEXTS, "message": message, "already_marked": result.already_marked},
        )

    return PrepareTomorrowResponse(
        task=TaskOut.model_validate(result.task),
        already_marked=result.already_marked,
        message=message,
    )
