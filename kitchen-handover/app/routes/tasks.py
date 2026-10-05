from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.i18n import TEXTS
from app.db.session import get_db
from app.schemas.preparation_task import CompleteTaskResponse, TaskOut
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/{task_id}/complete")
def complete_task(task_id: int, worker_id: int, request: Request, db: Session = Depends(get_db)):
    """worker_id as a query parameter — see products.prepare_tomorrow for why."""
    service = PreparationTaskService(db)
    result = service.complete_task(task_id, worker_id)

    message = TEXTS["already_completed_message"] if result.already_completed else TEXTS["completed_message"]

    if request.headers.get("hx-request") == "true":
        # Re-render the station's active task list so the completed item
        # disappears without a full page reload.
        station_id = result.task.product.station_id
        items = service.get_station_tasks_today(station_id)
        return templates.TemplateResponse(
            request,
            "_task_list.html",
            {
                "t": TEXTS,
                "station_id": station_id,
                "items": items,
                "flash_message": message,
                # The row template only ever reads worker.id (to build the
                # next FERTIG button's URL) — a plain dict is enough here,
                # we already know a worker acted since worker_id was required
                # to reach this point at all.
                "worker": {"id": worker_id},
            },
        )

    return CompleteTaskResponse(
        task=TaskOut.model_validate(result.task),
        already_completed=result.already_completed,
        message=message,
    )
