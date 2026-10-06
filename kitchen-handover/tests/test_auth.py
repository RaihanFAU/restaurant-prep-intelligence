"""Authentication, session, authorization, and identity/audit tests.

Numbered to match the task's required test list:
1-8  auth mechanics
9-11 identity/audit — the actual fix for the impersonation bug (a logged-in
     Raihan could previously complete a task and have it recorded as Ana)
"""

from app.core.enums import Role
from app.models import PreparationTask, Worker
from tests.factories import csrf_headers, login, make_product, make_station, make_worker

# ---------------------------------------------------------------------------
# 1-5: login / logout mechanics
# ---------------------------------------------------------------------------


def test_1_valid_login_succeeds(client, db_session):
    make_worker(db_session, email="raihan@example.test", password="correct-password")
    response = login(client, "raihan@example.test", "correct-password")
    assert response.status_code == 303
    assert "session" in response.cookies


def test_2_invalid_password_fails(client, db_session):
    make_worker(db_session, email="raihan@example.test", password="correct-password")
    response = login(client, "raihan@example.test", "wrong-password")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_3_unknown_email_fails(client, db_session):
    response = login(client, "nobody@example.test", "whatever")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_4_inactive_worker_cannot_login(client, db_session):
    make_worker(db_session, email="raihan@example.test", password="correct-password", is_active=False)
    response = login(client, "raihan@example.test", "correct-password")
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_5_logout_removes_session(client, db_session):
    make_station(db_session)
    make_worker(db_session, email="raihan@example.test", password="correct-password")
    login(client, "raihan@example.test", "correct-password")

    # logged in: home page works
    assert client.get("/").status_code == 200

    client.post("/logout", data={"csrf_token": client.cookies.get("csrf_token")}, follow_redirects=False)

    # the browser no longer carries a valid session -> redirected to /login
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


# ---------------------------------------------------------------------------
# 6-8: authorization
# ---------------------------------------------------------------------------


def test_6_unauthenticated_operational_request_is_rejected_or_redirected(client, db_session):
    station = make_station(db_session)
    make_product(db_session, station)

    # No login at all yet.
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_7_worker_cannot_access_admin(client, db_session):
    make_worker(db_session, email="worker@example.test", password="correct-password", role=Role.WORKER)
    login(client, "worker@example.test", "correct-password")

    response = client.get("/admin")
    assert response.status_code == 403


def test_8_admin_can_access_admin(client, db_session):
    make_worker(db_session, email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")

    response = client.get("/admin")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 9-11: identity / audit — the actual impersonation fix
# ---------------------------------------------------------------------------


def test_9_logged_in_raihan_completing_task_records_raihan(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    raihan = make_worker(db_session, display_name="Raihan", email="raihan@example.test", password="correct-password")
    login(client, "raihan@example.test", "correct-password")

    created = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client)).json()
    task_id = created["task"]["id"]

    client.post(f"/tasks/{task_id}/complete", headers=csrf_headers(client))

    task = db_session.get(PreparationTask, task_id)
    assert task.completed_by_id == raihan.id


def test_10_browser_cannot_spoof_completed_by_as_ana(client, db_session):
    """The old API accepted `?worker_id=`; the new one does not accept any
    client-supplied identity at all for this action — confirm that even an
    explicit attempt to pass one has no effect, because the route doesn't
    read it."""
    station = make_station(db_session)
    product = make_product(db_session, station)
    raihan = make_worker(db_session, display_name="Raihan", email="raihan@example.test", password="correct-password")
    ana = make_worker(db_session, display_name="Ana", email="ana@example.test", password="whatever")
    login(client, "raihan@example.test", "correct-password")

    created = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client)).json()
    task_id = created["task"]["id"]

    # Attempt to spoof identity via a query param the old API used to accept.
    client.post(f"/tasks/{task_id}/complete?worker_id={ana.id}", headers=csrf_headers(client))

    task = db_session.get(PreparationTask, task_id)
    assert task.completed_by_id == raihan.id
    assert task.completed_by_id != ana.id


def test_11_prepare_tomorrow_records_authenticated_current_worker(client, db_session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    ana = make_worker(db_session, display_name="Ana", email="ana@example.test", password="correct-password")
    login(client, "ana@example.test", "correct-password")

    created = client.post(
        f"/products/{product.id}/prepare-tomorrow?worker_id=999999", headers=csrf_headers(client)
    ).json()

    task = db_session.get(PreparationTask, created["task"]["id"])
    assert task.created_by_id == ana.id
