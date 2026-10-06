"""Unit tests for PreparationTaskService — the one business-logic module in
this slice. `today`/`now` are always passed explicitly so these tests never
depend on when they happen to run.

Covers the 15 scenarios required for this step (numbered in comments to
match docs/mvp/kitchen-handover.md's STEP 8 list).
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models import PreparationTask, PreparedProduct, Section, Station, Worker
from app.services.errors import InactiveProductError, ProductNotFoundError
from app.services.preparation_task_service import PreparationTaskService

TODAY = date(2026, 10, 4)
TOMORROW = TODAY + timedelta(days=1)
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture()
def worker(db_session: Session) -> Worker:
    # Placeholder password_hash — these are PreparationTaskService tests,
    # not auth tests (see test_auth.py), so a real Argon2 hash isn't needed.
    w = Worker(display_name="Michael", email="michael@example.test", password_hash="x")
    db_session.add(w)
    db_session.commit()
    return w


@pytest.fixture()
def pass_station(db_session: Session) -> Station:
    s = Station(name="PASS")
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture()
def grill_station(db_session: Session) -> Station:
    s = Station(name="GRILL")
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture()
def salat_section(db_session: Session, pass_station: Station) -> Section:
    sec = Section(station_id=pass_station.id, name="SALAT")
    db_session.add(sec)
    db_session.commit()
    return sec


@pytest.fixture()
def krautsalat(db_session: Session, pass_station: Station, salat_section: Section) -> PreparedProduct:
    p = PreparedProduct(name_de="Krautsalat", station_id=pass_station.id, section_id=salat_section.id)
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture()
def service(db_session: Session) -> PreparationTaskService:
    return PreparationTaskService(db_session)


# ---------------------------------------------------------------------------
# prepare_tomorrow
# ---------------------------------------------------------------------------


def test_1_prepare_tomorrow_creates_a_task(service, krautsalat, worker):
    result = service.prepare_tomorrow(krautsalat.id, worker.id, today=TODAY)

    assert result.already_marked is False
    assert result.task.id is not None
    assert result.task.status == TaskStatus.TO_PREPARE
    assert result.task.created_by_id == worker.id


def test_2_due_date_is_tomorrow(service, krautsalat, worker):
    result = service.prepare_tomorrow(krautsalat.id, worker.id, today=TODAY)
    assert result.task.due_date == TOMORROW


def test_3_duplicate_click_does_not_create_second_active_task(service, krautsalat, worker, db_session):
    first = service.prepare_tomorrow(krautsalat.id, worker.id, today=TODAY)
    second = service.prepare_tomorrow(krautsalat.id, worker.id, today=TODAY)

    assert first.already_marked is False
    assert second.already_marked is True
    assert second.task.id == first.task.id

    count = (
        db_session.query(PreparationTask)
        .filter_by(prepared_product_id=krautsalat.id, due_date=TOMORROW, status=TaskStatus.TO_PREPARE)
        .count()
    )
    assert count == 1


def test_4_inactive_product_cannot_be_marked(service, krautsalat, worker, db_session):
    krautsalat.is_active = False
    db_session.commit()

    with pytest.raises(InactiveProductError):
        service.prepare_tomorrow(krautsalat.id, worker.id, today=TODAY)


def test_prepare_tomorrow_rejects_nonexistent_product(service, worker):
    with pytest.raises(ProductNotFoundError):
        service.prepare_tomorrow(999999, worker.id, today=TODAY)


# ---------------------------------------------------------------------------
# get_station_tasks_today
# ---------------------------------------------------------------------------


def test_5_todays_task_appears_in_station_task_list(service, krautsalat, worker, db_session):
    db_session.add(PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id))
    db_session.commit()

    items = service.get_station_tasks_today(krautsalat.station_id, today=TODAY)

    assert len(items) == 1
    assert items[0].task.prepared_product_id == krautsalat.id
    assert items[0].is_overdue is False


def test_6_overdue_task_appears(service, krautsalat, worker, db_session):
    db_session.add(PreparationTask(prepared_product_id=krautsalat.id, due_date=YESTERDAY, created_by_id=worker.id))
    db_session.commit()

    items = service.get_station_tasks_today(krautsalat.station_id, today=TODAY)

    assert len(items) == 1
    assert items[0].is_overdue is True


def test_7_future_task_does_not_appear_in_todays_list(service, krautsalat, worker, db_session):
    db_session.add(
        PreparationTask(prepared_product_id=krautsalat.id, due_date=TOMORROW, created_by_id=worker.id)
    )
    db_session.commit()

    items = service.get_station_tasks_today(krautsalat.station_id, today=TODAY)

    assert items == []


def test_8_another_stations_task_does_not_appear(service, krautsalat, grill_station, worker, db_session):
    other_product = PreparedProduct(name_de="Leber", station_id=grill_station.id)
    db_session.add(other_product)
    db_session.commit()
    db_session.add(PreparationTask(prepared_product_id=other_product.id, due_date=TODAY, created_by_id=worker.id))
    db_session.add(PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id))
    db_session.commit()

    items = service.get_station_tasks_today(krautsalat.station_id, today=TODAY)

    assert len(items) == 1
    assert items[0].task.prepared_product_id == krautsalat.id


def test_9_overdue_tasks_sort_before_todays_tasks(service, pass_station, worker, db_session):
    # "Zucchini" would alphabetically sort after "Dijon Mayo" if it weren't
    # overdue — the overdue flag must dominate the sort, not the name.
    zucchini = PreparedProduct(name_de="Zucchini", station_id=pass_station.id)
    dijon = PreparedProduct(name_de="Dijon Mayo", station_id=pass_station.id)
    db_session.add_all([zucchini, dijon])
    db_session.commit()
    db_session.add(PreparationTask(prepared_product_id=dijon.id, due_date=TODAY, created_by_id=worker.id))
    db_session.add(PreparationTask(prepared_product_id=zucchini.id, due_date=YESTERDAY, created_by_id=worker.id))
    db_session.commit()

    items = service.get_station_tasks_today(pass_station.id, today=TODAY)

    assert [item.task.product.name_de for item in items] == ["Zucchini", "Dijon Mayo"]
    assert items[0].is_overdue is True
    assert items[1].is_overdue is False


def test_alphabetical_order_within_the_same_group(service, pass_station, worker, db_session):
    b_product = PreparedProduct(name_de="Bratkartoffeln", station_id=pass_station.id)
    a_product = PreparedProduct(name_de="Apfelmus", station_id=pass_station.id)
    db_session.add_all([b_product, a_product])
    db_session.commit()
    db_session.add(PreparationTask(prepared_product_id=b_product.id, due_date=TODAY, created_by_id=worker.id))
    db_session.add(PreparationTask(prepared_product_id=a_product.id, due_date=TODAY, created_by_id=worker.id))
    db_session.commit()

    items = service.get_station_tasks_today(pass_station.id, today=TODAY)

    assert [item.task.product.name_de for item in items] == ["Apfelmus", "Bratkartoffeln"]


# ---------------------------------------------------------------------------
# complete_task
# ---------------------------------------------------------------------------


def test_10_task_completion_changes_status(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()

    result = service.complete_task(task.id, worker.id, now=datetime(2026, 10, 4, 18, 0))

    assert result.task.status == TaskStatus.COMPLETED
    assert result.already_completed is False


def test_11_completed_at_is_populated(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()

    now = datetime(2026, 10, 4, 18, 30)
    result = service.complete_task(task.id, worker.id, now=now)

    assert result.task.completed_at == now


def test_12_completed_by_is_populated(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()

    result = service.complete_task(task.id, worker.id, now=datetime(2026, 10, 4, 18, 0))

    assert result.task.completed_by_id == worker.id


def test_13_completed_task_disappears_from_active_list(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()

    service.complete_task(task.id, worker.id, now=datetime(2026, 10, 4, 12, 0))

    items = service.get_station_tasks_today(krautsalat.station_id, today=TODAY)
    assert items == []


def test_14_completed_task_remains_in_database(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    service.complete_task(task_id, worker.id, now=datetime(2026, 10, 4, 12, 0))

    still_there = db_session.get(PreparationTask, task_id)
    assert still_there is not None
    assert still_there.status == TaskStatus.COMPLETED


def test_15_already_completed_task_is_safely_handled(service, krautsalat, worker, db_session):
    task = PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()

    first_completion_time = datetime(2026, 10, 4, 12, 0)
    first = service.complete_task(task.id, worker.id, now=first_completion_time)
    assert first.already_completed is False

    # A second tap (e.g. a double-tap on a slow connection) must not raise
    # and must not overwrite the original completion facts.
    second = service.complete_task(task.id, worker.id, now=datetime(2026, 10, 4, 23, 59))

    assert second.already_completed is True
    assert second.task.completed_at == first_completion_time
    assert second.task.completed_by_id == worker.id
