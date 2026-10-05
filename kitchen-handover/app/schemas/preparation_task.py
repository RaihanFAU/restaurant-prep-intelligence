from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import TaskStatus


class ProductRef(BaseModel):
    id: int
    name_de: str
    name_en: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskOut(BaseModel):
    id: int
    product: ProductRef
    due_date: date
    status: TaskStatus
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskListItemOut(BaseModel):
    task: TaskOut
    is_overdue: bool

    model_config = ConfigDict(from_attributes=True)


class StationTasksTodayResponse(BaseModel):
    station_id: int
    items: list[TaskListItemOut]


class PrepareTomorrowResponse(BaseModel):
    task: TaskOut
    already_marked: bool
    message: str


class CompleteTaskResponse(BaseModel):
    task: TaskOut
    already_completed: bool
    message: str
