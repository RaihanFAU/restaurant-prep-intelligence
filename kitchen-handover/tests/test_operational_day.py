"""The restaurant's operational (business) day doesn't reset at literal
calendar midnight — a worker going home at 00:30 and remembering
"Krautsalat needs to be ready for the morning" means the morning that's
about to start, not the one after that. Until the configured cutoff
(settings.operational_day_cutoff, dev default 04:00 Europe/Berlin), the
calendar has rolled over to a new date but the kitchen's working day
hasn't.

Also covers early completion: any active (TO_PREPARE) task — including
one still queued for tomorrow — can be completed whenever the worker
actually finishes it, not only once its due date arrives.

Numbered to match the task's required test list. 1-5 operational date,
6-10 Prepare Tomorrow semantics, 11-18 early completion. 19-24
(regression: overdue/today/duplicate-protection/priority/auth) are the
full existing suite, not new unit tests here.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from app.core.enums import TaskStatus
from app.core.operational_day import RESTAURANT_TIMEZONE, get_next_operational_due_date, get_operational_date
from app.models import PreparationTask
from app.services.preparation_task_service import PreparationTaskService
from tests.factories import csrf_headers, login, make_product, make_station, make_worker

TODAY = date(2026, 10, 9)
TOMORROW = TODAY + timedelta(days=1)


def _berlin(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=RESTAURANT_TIMEZONE)


# ---------------------------------------------------------------------------
# 1-5: operational date (default cutoff 04:00, from config)
# ---------------------------------------------------------------------------


def test_1_late_evening_is_same_operational_date():
    now = _berlin(2026, 10, 9, 23, 30)
    assert get_operational_date(now) == date(2026, 10, 9)


def test_2_just_after_midnight_before_cutoff_is_previous_operational_date():
    now = _berlin(2026, 10, 10, 0, 30)
    assert get_operational_date(now) == date(2026, 10, 9)


def test_3_one_minute_before_cutoff_is_previous_operational_date():
    now = _berlin(2026, 10, 10, 3, 59)
    assert get_operational_date(now) == date(2026, 10, 9)


def test_4_exactly_at_cutoff_is_new_operational_date():
    now = _berlin(2026, 10, 10, 4, 0)
    assert get_operational_date(now) == date(2026, 10, 10)


def test_5_after_cutoff_is_current_calendar_date():
    now = _berlin(2026, 10, 10, 8, 0)
    assert get_operational_date(now) == date(2026, 10, 10)


# ---------------------------------------------------------------------------
# 6-10: Prepare Tomorrow semantics
# ---------------------------------------------------------------------------


def test_6_late_evening_prepare_tomorrow_due_next_calendar_day():
    now = _berlin(2026, 10, 9, 23, 30)
    assert get_next_operational_due_date(now) == date(2026, 10, 10)


def test_7_after_midnight_before_cutoff_due_the_upcoming_morning():
    now = _berlin(2026, 10, 10, 0, 30)
    assert get_next_operational_due_date(now) == date(2026, 10, 10)


def test_8_three_fifty_nine_before_cutoff_due_the_upcoming_morning():
    now = _berlin(2026, 10, 10, 3, 59)
    assert get_next_operational_due_date(now) == date(2026, 10, 10)


def test_9_exactly_at_cutoff_due_the_day_after():
    now = _berlin(2026, 10, 10, 4, 0)
    assert get_next_operational_due_date(now) == date(2026, 10, 11)


def test_10_after_cutoff_due_the_day_after():
    now = _berlin(2026, 10, 10, 8, 0)
    assert get_next_operational_due_date(now) == date(2026, 10, 11)


def test_prepare_tomorrow_uses_operational_date_when_caller_omits_today(db_session):
    """Not in the numbered list, but the integration point the whole
    feature hinges on: the service actually calls get_operational_date()
    when a route doesn't pass today= explicitly (every real HTTP request).
    Tests 1-10 above only prove the standalone helper is correct in
    isolation."""
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)

    with patch("app.services.preparation_task_service.get_operational_date", return_value=date(2026, 10, 9)):
        result = service.prepare_tomorrow(product.id, worker.id)

    assert result.task.due_date == date(2026, 10, 10)


# ---------------------------------------------------------------------------
# 11-18: early completion
# ---------------------------------------------------------------------------


def test_11_to_14_tomorrow_task_can_be_completed_early(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)
    assert result.task.due_date == TOMORROW  # still due tomorrow

    completion_time = datetime(2026, 10, 9, 22, 30)
    complete_result = service.complete_task(result.task.id, worker.id, now=completion_time)

    assert complete_result.already_completed is False
    assert complete_result.task.status == TaskStatus.COMPLETED
    assert complete_result.task.due_date == TOMORROW  # 12: unchanged
    assert complete_result.task.completed_at == completion_time  # 13
    assert complete_result.task.completed_by_id == worker.id  # 14


def test_15_16_early_completed_task_disappears_from_tomorrow_queue_immediately(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    before = service.get_station_tasks_tomorrow(station.id, today=TODAY)
    assert len(before) == 1

    service.complete_task(result.task.id, worker.id)

    after = service.get_station_tasks_tomorrow(station.id, today=TODAY)
    assert after == []


def test_17_completed_future_task_does_not_reappear_when_due_date_arrives(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)
    service.complete_task(result.task.id, worker.id)

    items_on_due_date = service.get_station_tasks_today(station.id, today=TOMORROW)
    assert items_on_due_date == []


def test_18_completion_history_remains_available(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)
    service.complete_task(result.task.id, worker.id)

    all_tasks = service.list_all_tasks()
    assert any(t.id == result.task.id and t.status == TaskStatus.COMPLETED for t in all_tasks)


def test_tomorrow_row_has_done_button_and_completing_it_updates_the_tomorrow_section(client, db_session):
    """Route-level check for PART 6: the FERTIG button actually exists on
    a tomorrow-queue row (not just allowed at the service layer), and
    completing it re-renders the tomorrow section with the item gone."""
    station = make_station(db_session)
    product = make_product(db_session, station, "Remoulade")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")
    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    station_page = client.get(f"/stations/{station.id}")
    assert "FÜR MORGEN VORGEMERKT" in station_page.text
    assert "FERTIG" in station_page.text

    task = db_session.query(PreparationTask).filter_by(prepared_product_id=product.id).first()
    headers = csrf_headers(client)
    headers["HX-Request"] = "true"
    response = client.post(f"/tasks/{task.id}/complete", headers=headers)

    assert response.status_code == 200
    assert "Remoulade" not in response.text


# ---------------------------------------------------------------------------
# DST: operational date must stay correct across a Europe/Berlin transition
# ---------------------------------------------------------------------------


def test_operational_date_correct_across_dst_fallback():
    """2026-10-25 is the last Sunday of October — Germany's DST
    fall-back day (clocks go 03:00 CEST -> 02:00 CET). Both these local
    times are unambiguous (at/after 03:00 CET, past the ambiguous
    02:00-03:00 window), so this doesn't need `fold` handling — it just
    confirms the cutoff comparison still works correctly once the
    UTC offset itself has changed underneath it.
    """
    before_cutoff = _berlin(2026, 10, 25, 3, 30)
    assert get_operational_date(before_cutoff) == date(2026, 10, 24)

    after_cutoff = _berlin(2026, 10, 25, 4, 30)
    assert get_operational_date(after_cutoff) == date(2026, 10, 25)
