from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Date, Enum as SAEnum, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TaskPriority, TaskStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.prepared_product import PreparedProduct
    from app.models.worker import Worker


class PreparationTask(Base):
    """'Prepare this product by this date' — created by the PREPARE TOMORROW
    action, completed by a DONE tap.

    OVERDUE is never stored here — it's derived at query/display time from
    `due_date < today AND status != COMPLETED` (docs/mvp/kitchen-handover.md).

    The partial unique index below is the duplicate-task guard: pressing
    "prepare tomorrow" twice for the same product and the same due date must
    not create a second active task (spec §23/§26) — but an existing
    *overdue* task for an earlier due date does not block creating a new one
    for tomorrow, since they're different due_date values.
    """

    __tablename__ = "preparation_tasks"
    __table_args__ = (
        Index(
            "uq_active_task_per_product_due_date",
            "prepared_product_id",
            "due_date",
            unique=True,
            sqlite_where=text("status = 'TO_PREPARE'"),
            postgresql_where=text("status = 'TO_PREPARE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prepared_product_id: Mapped[int] = mapped_column(ForeignKey("prepared_products.id"), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=20, create_constraint=True, name="ck_task_status"),
        default=TaskStatus.TO_PREPARE,
        nullable=False,
    )

    # Simple manual priority (NOT the long-term weighted-scoring engine).
    # PREPARE TOMORROW defaults new tasks to URGENT (set explicitly by the
    # service, not relied on as just a column default); an admin may change
    # it. is_pinned is a separate, orthogonal "show this first no matter
    # what" flag — never folded into the priority enum as a 4th value
    # (spec: don't store PINNED as both a priority level and a boolean).
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority, native_enum=False, length=20, create_constraint=True, name="ck_task_priority"),
        default=TaskPriority.URGENT,
        nullable=False,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workers.id"), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["PreparedProduct"] = relationship(back_populates="tasks")
    created_by: Mapped["Worker"] = relationship(foreign_keys=[created_by_id])
    completed_by: Mapped[Optional["Worker"]] = relationship(foreign_keys=[completed_by_id])

    def __repr__(self) -> str:
        return (
            f"PreparationTask(id={self.id}, product_id={self.prepared_product_id}, "
            f"due_date={self.due_date}, status={self.status})"
        )
