from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.db.session import get_db
from app.models import Worker
from app.schemas.preparation_task import StationTasksTodayResponse, TaskListItemOut
from app.services.preparation_task_service import PreparationTaskService

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("/{station_id}/tasks/today", response_model=StationTasksTodayResponse)
def get_station_tasks_today(station_id: int, db: Session = Depends(get_db), current_user: Worker = Depends(require_user)):
    service = PreparationTaskService(db)
    items = service.get_station_tasks_today(station_id)
    return StationTasksTodayResponse(
        station_id=station_id,
        items=[TaskListItemOut.model_validate(item) for item in items],
    )
