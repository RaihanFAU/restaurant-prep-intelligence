from fastapi import APIRouter, Depends, Header, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.db.session import get_db
from app.models import Worker
from app.schemas.preparation_task import PrepareTomorrowResponse, TaskOut
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/{product_id}/prepare-tomorrow")
def prepare_tomorrow(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_user),
    x_csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
):
    """The acting worker is ALWAYS the authenticated session user
    (`current_user`), never a client-supplied value — this is the fix for
    the impersonation problem (a logged-in Raihan can no longer record an
    action as Ana)."""
    verify_csrf(request, x_csrf_token)

    service = PreparationTaskService(db)
    result = service.prepare_tomorrow(product_id, current_user.id)

    message = TEXTS["already_marked_message"] if result.already_marked else TEXTS["prepared_tomorrow_message"]

    if request.headers.get("hx-request") == "true":
        # Swap in the same persistent "already marked" fragment the
        # product page itself renders on a fresh GET — so the button
        # disappears and the checkmark state appears immediately,
        # without waiting for a reload, and a reload shows the exact
        # same thing because both read from the database.
        return templates.TemplateResponse(
            request,
            "_prepare_tomorrow_area.html",
            {"t": TEXTS, "product": result.task.product, "tomorrow_task": result.task, "status_message": message},
        )

    return PrepareTomorrowResponse(
        task=TaskOut.model_validate(result.task),
        already_marked=result.already_marked,
        message=message,
    )
