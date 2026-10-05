"""Route/integration tests — these exercise the real HTTP layer (FastAPI
TestClient) on top of the same in-memory DB as the unit tests, to catch
wiring mistakes the service-level tests can't see: URL paths, status codes,
JSON shapes, the worker cookie, and the HTMX vs. JSON content negotiation.

Business-rule edge cases (duplicate dedup, sorting, etc.) are already
covered precisely in test_preparation_task_service.py and are not repeated
here.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PreparedProduct, Station, Worker


def make_station(db_session: Session, name: str = "PASS") -> Station:
    station = Station(name=name)
    db_session.add(station)
    db_session.commit()
    return station


def make_product(db_session: Session, station: Station, name_de: str = "Krautsalat") -> PreparedProduct:
    product = PreparedProduct(name_de=name_de, station_id=station.id)
    db_session.add(product)
    db_session.commit()
    return product


def make_worker(db_session: Session, name: str = "Michael") -> Worker:
    worker = Worker(display_name=name)
    db_session.add(worker)
    db_session.commit()
    return worker


# ---------------------------------------------------------------------------
# JSON API round trip
# ---------------------------------------------------------------------------


def test_prepare_tomorrow_then_appears_in_station_tasks_today(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)

    response = client.post(f"/products/{product.id}/prepare-tomorrow", params={"worker_id": worker.id})
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
    worker = make_worker(db_session)

    first = client.post(f"/products/{product.id}/prepare-tomorrow", params={"worker_id": worker.id})
    second = client.post(f"/products/{product.id}/prepare-tomorrow", params={"worker_id": worker.id})

    assert first.json()["already_marked"] is False
    assert second.json()["already_marked"] is True
    assert second.status_code == 200


def test_complete_task_round_trip(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)

    created = client.post(f"/products/{product.id}/prepare-tomorrow", params={"worker_id": worker.id}).json()
    task_id = created["task"]["id"]

    response = client.post(f"/tasks/{task_id}/complete", params={"worker_id": worker.id})
    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "COMPLETED"
    assert body["already_completed"] is False

    again = client.post(f"/tasks/{task_id}/complete", params={"worker_id": worker.id})
    assert again.json()["already_completed"] is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_prepare_tomorrow_404_for_unknown_product(client: TestClient, db_session: Session):
    worker = make_worker(db_session)
    response = client.post("/products/999999/prepare-tomorrow", params={"worker_id": worker.id})
    assert response.status_code == 404


def test_prepare_tomorrow_400_for_inactive_product(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    product.is_active = False
    db_session.commit()
    worker = make_worker(db_session)

    response = client.post(f"/products/{product.id}/prepare-tomorrow", params={"worker_id": worker.id})
    assert response.status_code == 400


def test_station_tasks_today_404_for_unknown_station(client: TestClient):
    response = client.get("/stations/999999/tasks/today")
    assert response.status_code == 404


def test_complete_task_404_for_unknown_task(client: TestClient, db_session: Session):
    worker = make_worker(db_session)
    response = client.post("/tasks/999999/complete", params={"worker_id": worker.id})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


def test_home_page_renders(client: TestClient, db_session: Session):
    make_station(db_session, "PASS")
    response = client.get("/")
    assert response.status_code == 200
    assert "PASS" in response.text


def test_station_page_renders(client: TestClient, db_session: Session):
    station = make_station(db_session)
    make_product(db_session, station, "Krautsalat")
    response = client.get(f"/stations/{station.id}")
    assert response.status_code == 200
    assert "Krautsalat" in response.text


def test_product_page_renders(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station, "Krautsalat")
    response = client.get(f"/products/{product.id}")
    assert response.status_code == 200
    assert "Krautsalat" in response.text


def test_product_page_without_worker_prompts_to_choose_one_instead_of_the_action_button(
    client: TestClient, db_session: Session
):
    station = make_station(db_session)
    product = make_product(db_session, station, "Krautsalat")
    response = client.get(f"/products/{product.id}")
    assert response.status_code == 200
    assert "FÜR MORGEN VORBEREITEN" not in response.text
    assert "/worker/select" in response.text


# ---------------------------------------------------------------------------
# Worker "session" (no auth)
# ---------------------------------------------------------------------------


def test_worker_select_creates_new_worker_and_sets_cookie(client: TestClient, db_session: Session):
    response = client.post(
        "/worker/select",
        data={"next": "/", "new_name": "NewWorkerName"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "worker_id" in response.cookies

    worker = db_session.query(Worker).filter_by(display_name="NewWorkerName").first()
    assert worker is not None
    assert response.cookies["worker_id"] == str(worker.id)


def test_product_page_shows_prepare_button_once_worker_cookie_is_set(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)

    client.cookies.set("worker_id", str(worker.id))
    response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert f"/products/{product.id}/prepare-tomorrow?worker_id={worker.id}" in response.text


# ---------------------------------------------------------------------------
# HTMX fragment vs. JSON content negotiation
# ---------------------------------------------------------------------------


def test_prepare_tomorrow_returns_html_fragment_for_htmx_request(client: TestClient, db_session: Session):
    station = make_station(db_session)
    product = make_product(db_session, station)
    worker = make_worker(db_session)

    response = client.post(
        f"/products/{product.id}/prepare-tomorrow",
        params={"worker_id": worker.id},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Für morgen vorgemerkt." in response.text
