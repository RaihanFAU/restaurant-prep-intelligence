from fastapi import APIRouter, Depends, Header, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.core.csrf import verify_csrf
from app.core.i18n import TEXTS
from app.core.operational_day import get_operational_date
from app.db.session import get_db
from app.models import Worker
from app.schemas.preparation_task import CompleteTaskResponse, TaskOut
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/{task_id}/complete")
def complete_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Worker = Depends(require_user),
    x_csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
):
    """completed_by is always the authenticated session user — never a
    client-supplied worker_id (this was the exact impersonation bug being
    fixed: Raihan could previously complete a task and have it recorded as
    Ana)."""
    verify_csrf(request, x_csrf_token)

    service = PreparationTaskService(db)
    result = service.complete_task(task_id, current_user.id)

    message = TEXTS["already_completed_message"] if result.already_completed else TEXTS["completed_message"]

    if request.headers.get("hx-request") == "true":
        # Re-render whichever list this task actually belonged to, so the
        # completed item disappears without a full page reload. A task
        # can be completed early, straight out of the tomorrow queue
        # (PART 4/6) — in that case it's the tomorrow list that needs
        # updating, not today's (which never contained it).
        station_id = result.task.product.station_id
        if result.task.due_date > get_operational_date():
            tomorrow_items = service.get_station_tasks_tomorrow(station_id)
            return templates.TemplateResponse(
                request,
                "_tomorrow_task_list.html",
                {"t": TEXTS, "station_id": station_id, "tomorrow_items": tomorrow_items, "flash_message": message},
            )
        items = service.get_station_tasks_today(station_id)
        return templates.TemplateResponse(
            request,
            "_task_list.html",
            {"t": TEXTS, "station_id": station_id, "items": items, "flash_message": message},
        )

    return CompleteTaskResponse(
        task=TaskOut.model_validate(result.task),
        already_completed=result.already_completed,
        message=message,
    )
