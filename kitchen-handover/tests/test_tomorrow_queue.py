"""Tomorrow's "queued for handover" state must be visible immediately —
not just saved to the database and only shown once midnight rolls the
due_date into "today". PREPARE TOMORROW still creates a task with
due_date = tomorrow (that is NOT changing); what's new is a dedicated
tomorrow-only query/view so the home page, station page, and product page
all show it right away.

Numbered to match the task's required test list (1-11). Test 12 ("all
existing tests continue passing") is the full suite run, not a unit test
here.

Note on dates: there's no "Europe/Berlin helper" in this codebase to
reuse — the existing deterministic mechanism throughout
PreparationTaskService is already an explicit `today=` parameter (see
prepare_tomorrow/get_station_tasks_today), which the two new methods
here follow too. Service-level tests use that directly with a fixed
TODAY/TOMORROW. Route-level tests (hitting real HTTP endpoints, which
default to the real wall-clock date) don't need a fixed date at all: the
task is created and counted using the same real date.today() internally,
so they're deterministic regardless of which real day the suite runs on.
"""

from datetime import date, timedelta

from app.core.enums import TaskPriority, TaskStatus
from app.models import PreparationTask
from app.services.preparation_task_service import PreparationTaskService
from tests.factories import csrf_headers, login, make_product, make_station, make_worker

TODAY = date(2026, 10, 6)
TOMORROW = TODAY + timedelta(days=1)


def test_1_prepare_tomorrow_creates_tomorrow_task_immediately(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)

    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    assert result.already_marked is False
    assert result.task.due_date == TOMORROW
    assert result.task.status == TaskStatus.TO_PREPARE


def test_2_home_page_tomorrow_count_increases_immediately(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station, "Leber")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    response = client.get("/")
    assert "1 für morgen" in response.text


def test_3_todays_count_does_not_increase_for_tomorrow_only_task(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    today_response = client.get(f"/stations/{station.id}/tasks/today")
    assert today_response.json()["items"] == []


def test_4_station_page_shows_task_under_tomorrow_heading_immediately(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station, "Leber")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    response = client.get(f"/stations/{station.id}")
    assert "FÜR MORGEN VORGEMERKT" in response.text
    assert "Leber" in response.text


def test_5_product_page_shows_persisted_marked_state(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    response = client.get(f"/products/{product.id}")
    assert "FÜR MORGEN VORGEMERKT" in response.text
    # The button itself must be gone, not just a flash message alongside it.
    assert "FÜR MORGEN VORBEREITEN" not in response.text


def test_6_reloading_product_page_keeps_marked_state(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")
    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    first_reload = client.get(f"/products/{product.id}")
    second_reload = client.get(f"/products/{product.id}")
    assert "FÜR MORGEN VORGEMERKT" in first_reload.text
    assert "FÜR MORGEN VORGEMERKT" in second_reload.text


def test_7_clicking_prepare_tomorrow_twice_does_not_create_duplicate(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))
    second = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    assert second.json()["already_marked"] is True
    count = db_session.query(PreparationTask).filter_by(prepared_product_id=product.id).count()
    assert count == 1


def test_8_another_worker_clicking_same_product_does_not_create_duplicate(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session, display_name="Raihan", email="raihan@example.test")
    make_worker(db_session, display_name="Ana", email="ana@example.test")

    login(client, "raihan@example.test", "correct-password")
    client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    login(client, "ana@example.test", "correct-password")
    response = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    assert response.json()["already_marked"] is True
    count = db_session.query(PreparationTask).filter_by(prepared_product_id=product.id).count()
    assert count == 1


def test_9_tomorrow_task_does_not_appear_in_todays_list_before_due_date(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    items = service.get_station_tasks_today(station.id, today=TODAY)
    assert items == []


def test_10_task_appears_in_todays_list_once_date_advances_without_duplicating(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    # The calendar date advances to what was "tomorrow" — same row, no
    # duplicate, and it now qualifies for today's list.
    items = service.get_station_tasks_today(station.id, today=TOMORROW)
    assert len(items) == 1
    assert items[0].task.id == result.task.id

    count = db_session.query(PreparationTask).filter_by(prepared_product_id=product.id).count()
    assert count == 1


def test_11_priority_and_pin_changes_visible_while_still_due_tomorrow(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)
    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    service.set_priority(result.task.id, TaskPriority.NORMAL)
    service.set_pinned(result.task.id, True)

    items = service.get_station_tasks_tomorrow(station.id, today=TODAY)
    assert len(items) == 1
    assert items[0].task.priority == TaskPriority.NORMAL
    assert items[0].task.is_pinned is True
