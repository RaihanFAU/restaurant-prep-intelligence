"""Route/integration tests for the core workflow — now requiring real login
instead of the old worker_id query param / worker-selection cookie. Auth
mechanics themselves (login/logout/session/roles) are covered in
test_auth.py; this file focuses on the prepare-tomorrow -> task-list ->
complete workflow still working end to end on top of real auth.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import csrf_headers, login, make_product, make_station, make_worker


def test_prepare_tomorrow_then_appears_in_station_tasks_today(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    response = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["already_marked"] is False
    assert body["task"]["product"]["name_de"] == "Krautsalat"

    # A real 'tomorrow' task doesn't show up in *today's* list, by design —
    # bump the task's due_date back to simulate "today" for this check.
    task_id = body["task"]["id"]
    from app.models import PreparationTask

    task = db_session.get(PreparationTask, task_id)
    task.due_date = date.today()
    db_session.commit()

    today_response = client.get(f"/stations/{station.id}/tasks/today")
    assert today_response.status_code == 200
    today_body = today_response.json()
    assert len(today_body["items"]) == 1
    assert today_body["items"][0]["task"]["id"] == task_id
    assert today_body["items"][0]["is_overdue"] is False


def test_duplicate_prepare_tomorrow_returns_already_marked_not_an_error(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    first = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))
    second = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))

    assert first.json()["already_marked"] is False
    assert second.json()["already_marked"] is True
    assert second.status_code == 200


def test_complete_task_round_trip(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    created = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client)).json()
    task_id = created["task"]["id"]

    response = client.post(f"/tasks/{task_id}/complete", headers=csrf_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "COMPLETED"
    assert body["already_completed"] is False

    again = client.post(f"/tasks/{task_id}/complete", headers=csrf_headers(client))
    assert again.json()["already_completed"] is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_prepare_tomorrow_404_for_unknown_product(client: TestClient, db_session: Session):
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")
    response = client.post("/products/999999/prepare-tomorrow", headers=csrf_headers(client))
    assert response.status_code == 404


def test_prepare_tomorrow_400_for_inactive_product(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    product.is_active = False
    db_session.commit()
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    response = client.post(f"/products/{product.id}/prepare-tomorrow", headers=csrf_headers(client))
    assert response.status_code == 400


def test_station_tasks_today_404_for_unknown_station(client: TestClient, db_session: Session):
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")
    response = client.get("/stations/999999/tasks/today")
    assert response.status_code == 404


def test_complete_task_404_for_unknown_task(client: TestClient, db_session: Session):
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")
    response = client.post("/tasks/999999/complete", headers=csrf_headers(client))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


def test_home_page_renders(client: TestClient, db_session: Session):
    make_station(db_session, "PASS")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    response = client.get("/")
    assert response.status_code == 200
    assert "PASS" in response.text


def test_station_page_renders(client: TestClient, db_session: Session):
    station = make_station(db_session)
    make_product(db_session, station, "Krautsalat")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    response = client.get(f"/stations/{station.id}")
    assert response.status_code == 200
    assert "Krautsalat" in response.text


def test_product_page_renders(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station, "Krautsalat")
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    response = client.get(f"/products/{product.id}")
    assert response.status_code == 200
    assert "Krautsalat" in response.text
    assert "FÜR MORGEN VORBEREITEN" in response.text


# ---------------------------------------------------------------------------
# HTMX fragment vs. JSON content negotiation
# ---------------------------------------------------------------------------


def test_prepare_tomorrow_returns_html_fragment_for_htmx_request(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    make_worker(db_session)
    login(client, "michael@example.test", "correct-password")

    headers = csrf_headers(client)
    headers["HX-Request"] = "true"
    response = client.post(f"/products/{product.id}/prepare-tomorrow", headers=headers)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Für morgen vorgemerkt." in response.text
