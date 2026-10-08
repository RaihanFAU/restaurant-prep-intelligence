"""Worker PIN authentication: fast WORKER NAME + 4-digit PIN login as a
daily-use alternative to email+password, created and managed only by an
ADMIN. ADMIN accounts are untouched — they still authenticate with
email+password (test_auth.py), and a PIN can never grant ADMIN access.

Numbered to match the task's required test list (1-14). Test 15 ("all
existing tests still pass") is the full suite run, not a unit test here.
"""

from app.core.enums import Role
from app.core.security import hash_pin, verify_pin
from app.core.config import settings
from app.models import PreparationTask, Worker
from tests.factories import (
    csrf_form_field,
    csrf_headers,
    login,
    login_pin,
    make_product,
    make_station,
    make_worker,
    make_worker_pin,
)


def _login_admin(client, db_session):
    make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")


def test_1_admin_can_create_worker_with_pin(client, db_session):
    _login_admin(client, db_session)

    response = client.post(
        "/admin/users",
        data={
            "display_name": "Raihan", "email": "raihan@example.test",
            "pin": "1234", "confirm_pin": "1234", "role": "WORKER",
            **csrf_form_field(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    worker = db_session.query(Worker).filter_by(email="raihan@example.test").first()
    assert worker is not None
    assert worker.role == Role.WORKER
    assert worker.pin_hash is not None
    assert worker.password_hash is None


def test_2_pin_is_stored_hashed_never_plaintext(client, db_session):
    _login_admin(client, db_session)
    client.post(
        "/admin/users",
        data={
            "display_name": "Raihan", "email": "raihan@example.test",
            "pin": "1234", "confirm_pin": "1234", "role": "WORKER",
            **csrf_form_field(client),
        },
    )
    worker = db_session.query(Worker).filter_by(email="raihan@example.test").first()
    assert worker.pin_hash != "1234"
    assert "1234" not in worker.pin_hash
    assert worker.pin_hash.startswith("$argon2")
    assert verify_pin("1234", worker.pin_hash) is True


def test_3_pin_must_be_exactly_four_numeric_digits(client, db_session):
    _login_admin(client, db_session)

    for bad_pin in ("123", "12345", "abcd", "12a4"):
        response = client.post(
            "/admin/users",
            data={
                "display_name": "Raihan", "email": "raihan@example.test",
                "pin": bad_pin, "confirm_pin": bad_pin, "role": "WORKER",
                **csrf_form_field(client),
            },
        )
        assert response.status_code == 400
        assert db_session.query(Worker).filter_by(email="raihan@example.test").first() is None


def test_4_worker_can_login_with_correct_name_and_pin(client, db_session):
    make_worker_pin(db_session, display_name="Raihan", pin="1234")

    response = login_pin(client, "Raihan", "1234")
    assert response.status_code == 303
    assert "session" in response.cookies


def test_5_wrong_pin_is_rejected(client, db_session):
    make_worker_pin(db_session, display_name="Raihan", pin="1234")

    response = login_pin(client, "Raihan", "9999")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_6_inactive_worker_cannot_login_with_pin(client, db_session):
    make_worker_pin(db_session, display_name="Raihan", pin="1234", is_active=False)

    response = login_pin(client, "Raihan", "1234")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_7_worker_pin_flow_cannot_grant_admin_access(client, db_session):
    """Even if an ADMIN account somehow had a pin_hash set, the PIN login
    flow must still refuse it — ADMIN access requires email+password."""
    admin = make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    admin.pin_hash = hash_pin("1234")
    db_session.add(admin)
    db_session.commit()

    response = login_pin(client, "Admin", "1234")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_8_admin_still_logs_in_with_email_and_password(client, db_session):
    make_worker(db_session, email="admin@example.test", password="correct-password", role=Role.ADMIN)

    response = login(client, "admin@example.test", "correct-password")
    assert response.status_code == 303
    assert "session" in response.cookies


def test_9_authenticated_worker_identity_is_recorded_from_pin_session(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    raihan = make_worker_pin(db_session, display_name="Raihan", pin="1234")
    login_pin(client, "Raihan", "1234")

    created = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client)).json()
    task = db_session.get(PreparationTask, created["task"]["id"])
    assert task.created_by_id == raihan.id


def test_10_worker_cannot_complete_task_as_another_worker(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    raihan = make_worker_pin(db_session, display_name="Raihan", pin="1234")
    ana = make_worker_pin(db_session, display_name="Ana", email="ana-pin@example.test", pin="5678")
    login_pin(client, "Raihan", "1234")
    created = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client)).json()
    task_id = created["task"]["id"]

    login_pin(client, "Ana", "5678")
    # Attempt to spoof identity via a query param; the route never reads it.
    client.post(f"/tasks/{task_id}/complete?worker_id={raihan.id}", headers=csrf_headers(client))

    task = db_session.get(PreparationTask, task_id)
    assert task.completed_by_id == ana.id
    assert task.completed_by_id != raihan.id


def test_11_admin_can_reset_worker_pin(client, db_session):
    worker = make_worker_pin(db_session, display_name="Raihan", pin="1234")
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/users/{worker.id}/pin",
        data={"new_pin": "4321", "confirm_pin": "4321", **csrf_form_field(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(worker)
    assert verify_pin("4321", worker.pin_hash) is True


def test_12_old_pin_fails_after_reset(client, db_session):
    worker = make_worker_pin(db_session, display_name="Raihan", pin="1234")
    _login_admin(client, db_session)
    client.post(f"/admin/users/{worker.id}/pin", data={"new_pin": "4321", "confirm_pin": "4321", **csrf_form_field(client)})

    response = login_pin(client, "Raihan", "1234")
    assert response.status_code == 401


def test_13_new_pin_works_after_reset(client, db_session):
    worker = make_worker_pin(db_session, display_name="Raihan", pin="1234")
    _login_admin(client, db_session)
    client.post(f"/admin/users/{worker.id}/pin", data={"new_pin": "4321", "confirm_pin": "4321", **csrf_form_field(client)})

    response = login_pin(client, "Raihan", "4321")
    assert response.status_code == 303


def test_14_repeated_failed_pin_attempts_trigger_temporary_lockout(client, db_session):
    make_worker_pin(db_session, display_name="Raihan", pin="1234")

    for _ in range(settings.pin_max_failed_attempts):
        login_pin(client, "Raihan", "0000")

    # One more attempt, even with the correct PIN, must now be blocked.
    response = login_pin(client, "Raihan", "1234")
    assert response.status_code == 429
    assert "session" not in response.cookies
