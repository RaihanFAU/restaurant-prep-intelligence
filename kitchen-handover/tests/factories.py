"""Shared test helpers for the auth-aware test modules (test_auth.py,
test_admin_catalog.py, test_admin_users.py, test_priority.py, the rewritten
test_routes.py). Older test files (test_models.py,
test_preparation_task_service.py) predate this and keep their own small
inline helpers — not worth churning working tests just to switch helper
style.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import hash_password, hash_pin
from app.models import PreparedProduct, Station, Worker


def make_worker(
    db: Session, *, display_name: str = "Michael", email: str = "michael@example.test",
    password: str = "correct-password", role: Role = Role.WORKER, is_active: bool = True,
) -> Worker:
    worker = Worker(
        display_name=display_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(worker)
    db.commit()
    return worker


def make_worker_pin(
    db: Session, *, display_name: str = "Raihan", email: str = "raihan-pin@example.test",
    pin: str = "1234", role: Role = Role.WORKER, is_active: bool = True,
) -> Worker:
    """A WORKER account created the way /admin/users now creates them: with
    a PIN and no password at all (see test_worker_pin_auth.py)."""
    worker = Worker(
        display_name=display_name,
        email=email,
        pin_hash=hash_pin(pin),
        role=role,
        is_active=is_active,
    )
    db.add(worker)
    db.commit()
    return worker


def make_station(db: Session, name: str = "PASS") -> Station:
    station = Station(name=name)
    db.add(station)
    db.commit()
    return station


def make_product(db: Session, station: Station, name_de: str = "Krautsalat") -> PreparedProduct:
    product = PreparedProduct(name_de=name_de, station_id=station.id)
    db.add(product)
    db.commit()
    return product


def login(client: TestClient, email: str, password: str):
    """Logs the TestClient in — its cookie jar then carries the session
    (and the csrf_token cookie) for subsequent requests, same as a real
    browser."""
    # A GET first, purely to receive the csrf_token cookie the middleware
    # sets on first contact (a real browser would have it from any earlier
    # page view; a fresh TestClient has made no requests yet).
    client.get("/login")
    csrf_token = client.cookies.get("csrf_token")
    return client.post(
        "/login",
        data={"email": email, "password": password, "next": "/", "csrf_token": csrf_token},
        follow_redirects=False,
    )


def login_pin(client: TestClient, display_name: str, pin: str):
    """Same idea as login(), for the WORKER NAME + PIN flow."""
    client.get("/worker-login")
    csrf_token = client.cookies.get("csrf_token")
    return client.post(
        "/worker-login",
        data={"display_name": display_name, "pin": pin, "next": "/", "csrf_token": csrf_token},
        follow_redirects=False,
    )


def csrf_headers(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


def csrf_form_field(client: TestClient) -> dict:
    return {"csrf_token": client.cookies.get("csrf_token")}
