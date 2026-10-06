from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import TaskPriority, TaskStatus
from app.models import PreparationTask, PreparedProduct


def get_task(db: Session, task_id: int) -> PreparationTask | None:
    return db.get(PreparationTask, task_id)


def find_active_task(db: Session, product_id: int, due_date: date) -> PreparationTask | None:
    """The task that the partial unique index would conflict with, if a new
    one were created for the same (product, due_date) while status is still
    TO_PREPARE."""
    stmt = select(PreparationTask).where(
        PreparationTask.prepared_product_id == product_id,
        PreparationTask.due_date == due_date,
        PreparationTask.status == TaskStatus.TO_PREPARE,
    )
    return db.scalars(stmt).first()


def create_task(
    db: Session, *, product_id: int, due_date: date, created_by_id: int, priority: TaskPriority
) -> PreparationTask:
    task = PreparationTask(
        prepared_product_id=product_id,
        due_date=due_date,
        status=TaskStatus.TO_PREPARE,
        created_by_id=created_by_id,
        priority=priority,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_all_tasks(db: Session) -> list[PreparationTask]:
    """Admin view (/admin/tasks) — every task, any status, any station,
    newest first."""
    stmt = (
        select(PreparationTask)
        .options(joinedload(PreparationTask.product), joinedload(PreparationTask.created_by), joinedload(PreparationTask.completed_by))
        .order_by(PreparationTask.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def save(db: Session, task: PreparationTask) -> PreparationTask:
    """Persist in-place edits (priority, is_pinned) made by the caller."""
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_station_tasks_today(db: Session, station_id: int, today: date) -> list[PreparationTask]:
    """Active tasks for a station due today or earlier — intentionally
    includes overdue tasks. Sorting (overdue first, then alphabetical) is a
    display concern handled by the service, not here."""
    stmt = (
        select(PreparationTask)
        .join(PreparedProduct, PreparationTask.prepared_product_id == PreparedProduct.id)
        .where(
            PreparedProduct.station_id == station_id,
            PreparationTask.status == TaskStatus.TO_PREPARE,
            PreparationTask.due_date <= today,
        )
        .options(joinedload(PreparationTask.product))
    )
    return list(db.scalars(stmt).unique())


def mark_completed(
    db: Session, task: PreparationTask, *, completed_by_id: int, completed_at: datetime
) -> PreparationTask:
    task.status = TaskStatus.COMPLETED
    task.completed_at = completed_at
    task.completed_by_id = completed_by_id
    db.commit()
    db.refresh(task)
    return task
