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

from app.core.enums import TaskPriority, TaskStatus
from app.core.operational_day import get_operational_date
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

# Lower rank sorts first. Display/sort-only concept — not a model concern,
# so it lives here rather than on the enum itself.
_PRIORITY_RANK = {TaskPriority.URGENT: 0, TaskPriority.HIGH: 1, TaskPriority.NORMAL: 2}


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

        today defaults to the restaurant's current *operational* day
        (app/core/operational_day.py), not literal calendar today — a
        worker pressing this at 00:30 means "the upcoming morning", not
        the one after. Tests pass today explicitly so this is
        deterministic instead of depending on the real clock.
        """
        today = today or get_operational_date()

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
                self.db,
                product_id=product_id,
                due_date=due_date,
                created_by_id=worker_id,
                # A product only gets "prepare tomorrow"'d because someone on
                # the floor noticed it's finished — that's inherently urgent,
                # not a judgment call left to a column default. An admin can
                # still downgrade it afterward via /admin/tasks.
                priority=TaskPriority.URGENT,
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
        """status = TO_PREPARE AND due_date <= today (intentionally includes
        overdue tasks), ordered:

            1. pinned tasks first (always — a pin overrides every other
               criterion below, including priority and overdue-ness)
            2. overdue before today's
            3. priority: URGENT, then HIGH, then NORMAL
            4. product name, alphabetically, as a stable final tiebreaker

        This exact order is asserted in tests/test_preparation_task_service.py
        (see test_pinned_task_sorts_before_everything_else and friends) —
        change the sort key there too if this ordering ever changes.
        """
        today = today or get_operational_date()

        station = station_repository.get_station(self.db, station_id)
        if station is None:
            raise StationNotFoundError(station_id)

        tasks = preparation_task_repository.get_station_tasks_today(self.db, station_id, today)
        items = [TaskListItem(task=t, is_overdue=t.due_date < today) for t in tasks]
        items.sort(
            key=lambda item: (
                0 if item.task.is_pinned else 1,
                0 if item.is_overdue else 1,
                _PRIORITY_RANK[item.task.priority],
                item.task.product.name_de.lower(),
            )
        )
        return items

    def get_station_tasks_tomorrow(self, station_id: int, today: date | None = None) -> list[TaskListItem]:
        """status = TO_PREPARE AND due_date == today + 1 day — the "queued
        for tomorrow" handover state, shown separately from
        get_station_tasks_today so a worker sees immediately that
        something was prepped for the next shift, without it being
        mistaken for something actionable right now. Deliberately never
        includes anything due today or overdue (that's the other method),
        and never requires waiting for midnight — it's a live DB query,
        correct the instant the task is created.
        """
        today = today or get_operational_date()
        tomorrow = today + timedelta(days=1)

        station = station_repository.get_station(self.db, station_id)
        if station is None:
            raise StationNotFoundError(station_id)

        tasks = preparation_task_repository.get_station_tasks_tomorrow(self.db, station_id, tomorrow)
        items = [TaskListItem(task=t, is_overdue=False) for t in tasks]
        items.sort(
            key=lambda item: (
                0 if item.task.is_pinned else 1,
                _PRIORITY_RANK[item.task.priority],
                item.task.product.name_de.lower(),
            )
        )
        return items

    def get_active_tomorrow_task(self, product_id: int, today: date | None = None) -> PreparationTask | None:
        """Does this product already have an active (TO_PREPARE) task
        queued for tomorrow? Drives the product page's persistent
        "already marked" state — read fresh from the database on every
        request, so it's correct after a reload or for a different
        worker opening the same page, not just right after the button
        was clicked."""
        today = today or get_operational_date()
        tomorrow = today + timedelta(days=1)
        return preparation_task_repository.find_active_task(self.db, product_id, tomorrow)

    def set_priority(self, task_id: int, priority: TaskPriority) -> PreparationTask:
        """Admin-only in practice (enforced at the route layer, not here —
        this service has no concept of roles)."""
        task = preparation_task_repository.get_task(self.db, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        task.priority = priority
        return preparation_task_repository.save(self.db, task)

    def set_pinned(self, task_id: int, is_pinned: bool) -> PreparationTask:
        task = preparation_task_repository.get_task(self.db, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        task.is_pinned = is_pinned
        return preparation_task_repository.save(self.db, task)

    def create_manual_task(
        self, product_id: int, due_date: date, priority: TaskPriority, created_by_id: int
    ) -> PrepareTomorrowResult:
        """Admin manual task creation (/admin/tasks) — same duplicate-guard
        and validation rules as prepare_tomorrow, but the caller picks the
        due date and priority explicitly instead of them being implied by
        "tomorrow" / "urgent"."""
        product = prepared_product_repository.get_product(self.db, product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not product.is_active:
            raise InactiveProductError(product_id)

        existing = preparation_task_repository.find_active_task(self.db, product_id, due_date)
        if existing is not None:
            return PrepareTomorrowResult(task=existing, already_marked=True)

        try:
            task = preparation_task_repository.create_task(
                self.db, product_id=product_id, due_date=due_date, created_by_id=created_by_id, priority=priority
            )
        except IntegrityError:
            self.db.rollback()
            existing = preparation_task_repository.find_active_task(self.db, product_id, due_date)
            if existing is None:  # pragma: no cover - should be unreachable
                raise
            return PrepareTomorrowResult(task=existing, already_marked=True)

        return PrepareTomorrowResult(task=task, already_marked=False)

    def list_all_tasks(self) -> list[PreparationTask]:
        """Admin task list (/admin/tasks) — every task, unfiltered, unsorted
        beyond newest-first (an admin reviewing/managing tasks wants to see
        everything, not the worker-facing actionable subset)."""
        return preparation_task_repository.list_all_tasks(self.db)

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
