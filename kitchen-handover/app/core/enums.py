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


class Role(str, enum.Enum):
    """Account role. Deliberately just two — nothing in this MVP needs a
    third MANAGER tier yet (reviewed and discarded when this was built:
    see docs/mvp/kitchen-handover.md change log). Add one later only when a
    real permission actually needs to sit strictly between these two."""

    ADMIN = "ADMIN"
    WORKER = "WORKER"


class TaskPriority(str, enum.Enum):
    """Manually-set priority — NOT the long-term system's weighted scoring
    engine (docs/preparation-engine.md). Just three levels, plus the
    separate `is_pinned` flag on PreparationTask for "show this first no
    matter what" (spec: don't conflate PINNED into this enum as a 4th
    value — pinning is orthogonal to priority, not a level of it)."""

    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
