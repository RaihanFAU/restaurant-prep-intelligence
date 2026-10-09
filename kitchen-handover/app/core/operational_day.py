"""What "today" means for scheduling purposes — the restaurant's
operational/business day, not literal calendar midnight.

A kitchen's working day doesn't reset at 00:00: a worker going home at
00:30 and suddenly remembering "Krautsalat needs to be ready for the
morning" means the morning that's about to start, not the one after
that. Until the configured cutoff (settings.operational_day_cutoff,
development default 04:00 Europe/Berlin — a placeholder, not confirmed
restaurant truth), the calendar has already rolled over to a new date
but the *business* day hasn't.

This is the one place that concept lives. Every piece of scheduling
logic that needs "today" (PREPARE TOMORROW, today/overdue queries, the
tomorrow queue, home counters) resolves it through
get_operational_date() here instead of calling date.today() directly —
see PreparationTaskService and its "today: date | None = None" params,
which already default to the real clock when a caller (a route) doesn't
pass one explicitly. Tests that need a fixed date still pass one
explicitly and are entirely unaffected by any of this.

created_at / completed_at are NOT touched by any of this, deliberately —
those remain plain, actual-moment-in-time timestamps (see
PreparationTaskService.complete_task). Operational date is only ever
used for due_date / "is this today, tomorrow, or overdue" comparisons,
never to reinterpret when something historically happened.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

RESTAURANT_TIMEZONE = ZoneInfo("Europe/Berlin")


def get_restaurant_now() -> datetime:
    """The current moment as a timezone-aware datetime in the
    restaurant's local timezone — never a naive datetime.now(), which
    would silently depend on whatever timezone the server process
    happens to be running in rather than the restaurant's actual one."""
    return datetime.now(RESTAURANT_TIMEZONE)


def get_operational_date(now: datetime | None = None) -> date:
    """The restaurant's current business day. Before the configured
    cutoff, the clock has already crossed into a new calendar date but
    the kitchen's working day hasn't, so it still counts as the
    previous calendar date.
    """
    now = now or get_restaurant_now()
    if now.time() < settings.operational_day_cutoff:
        return now.date() - timedelta(days=1)
    return now.date()


def get_next_operational_due_date(now: datetime | None = None) -> date:
    """What "Prepare Tomorrow" means right now: the day after the
    current operational day — the next time the kitchen's working day
    begins, not necessarily the next calendar date."""
    return get_operational_date(now) + timedelta(days=1)
