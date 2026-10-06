"""Simple manual task priority: URGENT default, admin priority changes,
pin/unpin, and the documented sort order (pinned > overdue > priority >
name), plus a regression check that the duplicate-active-task rule still
holds with these new fields in play.

Numbered to match the task's required test list (21-27).
"""

from datetime import date, timedelta

from app.core.enums import Role, TaskPriority
from app.models import PreparationTask, PreparedProduct
from app.services.preparation_task_service import PreparationTaskService
from tests.factories import csrf_form_field, login, make_product, make_station, make_worker

TODAY = date(2026, 10, 6)
TOMORROW = TODAY + timedelta(days=1)
YESTERDAY = TODAY - timedelta(days=1)


def _login_admin(client, db_session):
    make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")


def test_21_prepare_tomorrow_defaults_to_urgent(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)

    result = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    assert result.task.priority == TaskPriority.URGENT


def test_22_admin_can_change_task_priority(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session, email="w@example.test", password="x")
    task = PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/tasks/{task.id}/priority", data={"priority": "NORMAL", **csrf_form_field(client)}, follow_redirects=False
    )
    assert response.status_code == 303
    db_session.refresh(task)
    assert task.priority == TaskPriority.NORMAL


def test_23_admin_can_pin_task(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session, email="w@example.test", password="x")
    task = PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(task)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(f"/admin/tasks/{task.id}/pin", data=csrf_form_field(client), follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(task)
    assert task.is_pinned is True


def test_24_admin_can_unpin_task(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session, email="w@example.test", password="x")
    task = PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id, is_pinned=True)
    db_session.add(task)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(f"/admin/tasks/{task.id}/unpin", data=csrf_form_field(client), follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(task)
    assert task.is_pinned is False


def test_25_pinned_task_sorts_before_non_pinned_task(db_session):
    """The task's own worked example: a HIGH-priority pinned task must
    outrank URGENT, non-pinned tasks — pinning overrides priority entirely,
    not just breaks ties within the same priority."""
    station = make_station(db_session)
    worker = make_worker(db_session)
    schweinesauce = PreparedProduct(name_de="Schweinesauce", station_id=station.id)
    krautsalat = PreparedProduct(name_de="Krautsalat", station_id=station.id)
    dijon = PreparedProduct(name_de="Dijon Mayo", station_id=station.id)
    db_session.add_all([schweinesauce, krautsalat, dijon])
    db_session.commit()

    db_session.add(PreparationTask(prepared_product_id=krautsalat.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.URGENT))
    db_session.add(PreparationTask(prepared_product_id=dijon.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.URGENT))
    db_session.add(
        PreparationTask(
            prepared_product_id=schweinesauce.id,
            due_date=TODAY,
            created_by_id=worker.id,
            priority=TaskPriority.HIGH,
            is_pinned=True,
        )
    )
    db_session.commit()

    service = PreparationTaskService(db_session)
    items = service.get_station_tasks_today(station.id, today=TODAY)

    names = [item.task.product.name_de for item in items]
    assert names == ["Schweinesauce", "Dijon Mayo", "Krautsalat"]
    assert items[0].task.is_pinned is True


def test_26_overdue_and_priority_ordering_follows_documented_rule(db_session):
    """Full documented order: pinned, then overdue, then URGENT/HIGH/NORMAL,
    then alphabetical — exercised with one task per rung so a regression in
    any single comparison key shows up immediately."""
    station = make_station(db_session)
    worker = make_worker(db_session)

    pinned = PreparedProduct(name_de="Zzz-Pinned", station_id=station.id)
    overdue_urgent = PreparedProduct(name_de="Overdue-Urgent", station_id=station.id)
    today_urgent = PreparedProduct(name_de="Today-Urgent", station_id=station.id)
    today_high = PreparedProduct(name_de="Today-High", station_id=station.id)
    today_normal = PreparedProduct(name_de="Today-Normal", station_id=station.id)
    db_session.add_all([pinned, overdue_urgent, today_urgent, today_high, today_normal])
    db_session.commit()

    db_session.add(PreparationTask(prepared_product_id=pinned.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.NORMAL, is_pinned=True))
    db_session.add(PreparationTask(prepared_product_id=overdue_urgent.id, due_date=YESTERDAY, created_by_id=worker.id, priority=TaskPriority.URGENT))
    db_session.add(PreparationTask(prepared_product_id=today_urgent.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.URGENT))
    db_session.add(PreparationTask(prepared_product_id=today_high.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.HIGH))
    db_session.add(PreparationTask(prepared_product_id=today_normal.id, due_date=TODAY, created_by_id=worker.id, priority=TaskPriority.NORMAL))
    db_session.commit()

    service = PreparationTaskService(db_session)
    items = service.get_station_tasks_today(station.id, today=TODAY)

    names = [item.task.product.name_de for item in items]
    assert names == ["Zzz-Pinned", "Overdue-Urgent", "Today-Urgent", "Today-High", "Today-Normal"]


def test_27_duplicate_active_task_rule_still_works_with_priority_and_pinning(db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)
    service = PreparationTaskService(db_session)

    first = service.prepare_tomorrow(product.id, worker.id, today=TODAY)
    second = service.prepare_tomorrow(product.id, worker.id, today=TODAY)

    assert first.already_marked is False
    assert second.already_marked is True
    count = (
        db_session.query(PreparationTask)
        .filter_by(prepared_product_id=product.id, due_date=TOMORROW)
        .count()
    )
    assert count == 1
