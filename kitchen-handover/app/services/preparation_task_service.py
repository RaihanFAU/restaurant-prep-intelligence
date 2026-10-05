"""The one business-logic module for this MVP slice: PREPARE TOMORROW ->
today's/overdue task list -> COMPLETE TASK.

Routes and templates should never touch SQLAlchemy directly for this
workflow — they call this service, which calls the repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models import PreparationTask
from app.repositories import (
    prepared_product_repository,
    preparation_task_repository,
    station_repository,
    worker_repository,
)
from app.services.errors import (
    InactiveProductError,
    ProductNotFoundError,
    StationNotFoundError,
    TaskNotFoundError,
    WorkerNotFoundError,
)


@dataclass
class PrepareTomorrowResult:
    task: PreparationTask
    already_marked: bool
    """True if an active task for this product/due_date already existed —
    the caller should show a friendly 'already marked' message, not treat
    this as an error."""


@dataclass
class CompleteTaskResult:
    task: PreparationTask
    already_completed: bool
    """True if the task was already COMPLETED before this call — handled
    safely (idempotent no-op) rather than raising, so a double-tap on DONE
    (easy to do on a phone) never produces an error."""


@dataclass
class TaskListItem:
    task: PreparationTask
    is_overdue: bool


class PreparationTaskService:
    def __init__(self, db: Session):
        self.db = db

    def prepare_tomorrow(self, product_id: int, worker_id: int, today: date | None = None) -> PrepareTomorrowResult:
        """Mark a product for preparation tomorrow.

        today defaults to the real current date; tests pass it explicitly
        so "tomorrow" is deterministic instead of depending on when the
        test happens to run.
        """
        today = today or date.today()

        product = prepared_product_repository.get_product(self.db, product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not product.is_active:
            raise InactiveProductError(product_id)

        worker = worker_repository.get_worker(self.db, worker_id)
        if worker is None:
            raise WorkerNotFoundError(worker_id)

        due_date = today + timedelta(days=1)

        existing = preparation_task_repository.find_active_task(self.db, product_id, due_date)
        if existing is not None:
            return PrepareTomorrowResult(task=existing, already_marked=True)

        try:
            task = preparation_task_repository.create_task(
                self.db, product_id=product_id, due_date=due_date, created_by_id=worker_id
            )
        except IntegrityError:
            # Two near-simultaneous taps both passed the check above before
            # either committed; the partial unique index is the real guard
            # here. Roll back our failed insert and return the row that won
            # the race, same friendly result as a normal duplicate.
            self.db.rollback()
            existing = preparation_task_repository.find_active_task(self.db, product_id, due_date)
            if existing is None:  # pragma: no cover - should be unreachable
                raise
            return PrepareTomorrowResult(task=existing, already_marked=True)

        return PrepareTomorrowResult(task=task, already_marked=False)

    def get_station_tasks_today(self, station_id: int, today: date | None = None) -> list[TaskListItem]:
        """status = TO_PREPARE AND due_date <= today, overdue first, then
        today's tasks, then alphabetical by product name."""
        today = today or date.today()

        station = station_repository.get_station(self.db, station_id)
        if station is None:
            raise StationNotFoundError(station_id)

        tasks = preparation_task_repository.get_station_tasks_today(self.db, station_id, today)
        items = [TaskListItem(task=t, is_overdue=t.due_date < today) for t in tasks]
        items.sort(key=lambda item: (0 if item.is_overdue else 1, item.task.product.name_de.lower()))
        return items

    def complete_task(self, task_id: int, worker_id: int, now: datetime | None = None) -> CompleteTaskResult:
        now = now or datetime.now()

        task = preparation_task_repository.get_task(self.db, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        if task.status == TaskStatus.COMPLETED:
            return CompleteTaskResult(task=task, already_completed=True)

        worker = worker_repository.get_worker(self.db, worker_id)
        if worker is None:
            raise WorkerNotFoundError(worker_id)

        task = preparation_task_repository.mark_completed(
            self.db, task, completed_by_id=worker_id, completed_at=now
        )
        return CompleteTaskResult(task=task, already_completed=False)
