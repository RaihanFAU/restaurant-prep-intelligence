import enum


class TaskStatus(str, enum.Enum):
    """Status of a PreparationTask.

    OVERDUE is intentionally not a stored status — it is derived wherever
    tasks are displayed, as `due_date < today AND status != COMPLETED`
    (see docs/mvp/kitchen-handover.md §17 of the original prompt / the MVP
    spec's "derived, not stored" rule).
    """

    TO_PREPARE = "TO_PREPARE"
    COMPLETED = "COMPLETED"
