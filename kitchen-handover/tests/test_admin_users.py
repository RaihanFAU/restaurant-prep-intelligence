"""Admin user management: creation, duplicate email rejection, and
confirming passwords are genuinely hashed (never stored or ever
retrievable as plaintext).

Numbered to match the task's required test list (18-20). Also covers the
"don't lock everyone out" last-admin protection, which the task's "Part 7"
calls for even though it isn't in the numbered test list.
"""

from app.core.enums import Role
from app.core.security import verify_password
from app.models import Worker
from tests.factories import csrf_form_field, login, make_worker


def _login_admin(client, db_session):
    make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")


def test_18_admin_can_create_worker(client, db_session):
    _login_admin(client, db_session)

    response = client.post(
        "/admin/users",
        data={
            "display_name": "Raihan",
            "email": "raihan@example.test",
            "password": "a-real-password",
            "role": "WORKER",
            **csrf_form_field(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    worker = db_session.query(Worker).filter_by(email="raihan@example.test").first()
    assert worker is not None
    assert worker.display_name == "Raihan"
    assert worker.role == Role.WORKER


def test_19_duplicate_email_rejected(client, db_session):
    make_worker(db_session, display_name="Existing", email="taken@example.test", password="whatever")
    _login_admin(client, db_session)

    response = client.post(
        "/admin/users",
        data={
            "display_name": "Someone New",
            "email": "taken@example.test",
            "password": "another-password",
            "role": "WORKER",
            **csrf_form_field(client),
        },
    )
    assert response.status_code == 400
    assert db_session.query(Worker).filter_by(email="taken@example.test").count() == 1


def test_20_password_is_stored_hashed_never_plaintext(client, db_session):
    _login_admin(client, db_session)

    client.post(
        "/admin/users",
        data={
            "display_name": "Raihan",
            "email": "raihan@example.test",
            "password": "super-secret-value",
            "role": "WORKER",
            **csrf_form_field(client),
        },
    )

    worker = db_session.query(Worker).filter_by(email="raihan@example.test").first()
    assert worker.password_hash != "super-secret-value"
    assert "super-secret-value" not in worker.password_hash
    assert worker.password_hash.startswith("$argon2")
    assert verify_password("super-secret-value", worker.password_hash) is True


def test_worker_cannot_create_users(client, db_session):
    make_worker(db_session, email="worker@example.test", password="correct-password", role=Role.WORKER)
    login(client, "worker@example.test", "correct-password")

    response = client.post(
        "/admin/users",
        data={
            "display_name": "Raihan",
            "email": "raihan@example.test",
            "password": "whatever",
            "role": "ADMIN",
            **csrf_form_field(client),
        },
    )
    assert response.status_code == 403


def test_cannot_deactivate_the_only_remaining_admin(client, db_session):
    admin = make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")

    response = client.post(f"/admin/users/{admin.id}/deactivate", data=csrf_form_field(client))
    assert response.status_code == 400
    db_session.refresh(admin)
    assert admin.is_active is True


def test_can_deactivate_an_admin_when_another_active_admin_remains(client, db_session):
    make_worker(db_session, display_name="Admin One", email="admin1@example.test", password="correct-password", role=Role.ADMIN)
    admin_two = make_worker(db_session, display_name="Admin Two", email="admin2@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin1@example.test", "correct-password")

    response = client.post(f"/admin/users/{admin_two.id}/deactivate", data=csrf_form_field(client), follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(admin_two)
    assert admin_two.is_active is False
