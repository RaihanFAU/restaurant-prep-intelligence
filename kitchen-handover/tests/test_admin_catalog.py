"""Admin product/station/section management — creation, editing,
deactivation, and the station/section validation rule, plus confirming a
WORKER (not just an anonymous client) is blocked from the admin endpoints.

Numbered to match the task's required test list (12-17).
"""

from app.core.enums import Role
from app.models import PreparedProduct, Section, Station
from tests.factories import csrf_form_field, login, make_station, make_worker


def _login_admin(client, db_session):
    admin = make_worker(db_session, display_name="Admin", email="admin@example.test", password="correct-password", role=Role.ADMIN)
    login(client, "admin@example.test", "correct-password")
    return admin


def test_12_admin_can_create_product(client, db_session):
    station = make_station(db_session)
    _login_admin(client, db_session)

    response = client.post(
        "/admin/products",
        data={"name_de": "Remoulade", "name_en": "", "station_id": station.id, "section_id": "", **csrf_form_field(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    product = db_session.query(PreparedProduct).filter_by(name_de="Remoulade").first()
    assert product is not None
    assert product.station_id == station.id


def test_13_worker_cannot_create_product_through_admin_endpoint(client, db_session):
    station = make_station(db_session)
    make_worker(db_session, email="worker@example.test", password="correct-password", role=Role.WORKER)
    login(client, "worker@example.test", "correct-password")

    response = client.post(
        "/admin/products",
        data={"name_de": "Remoulade", "name_en": "", "station_id": station.id, "section_id": "", **csrf_form_field(client)},
    )
    assert response.status_code == 403
    assert db_session.query(PreparedProduct).filter_by(name_de="Remoulade").first() is None


def test_14_admin_can_edit_product(client, db_session):
    station = make_station(db_session)
    other_station = make_station(db_session, "GRILL")
    product = PreparedProduct(name_de="Krautsalat", station_id=station.id)
    db_session.add(product)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/products/{product.id}/edit",
        data={
            "name_de": "Krautsalat (neu)",
            "name_en": "Coleslaw",
            "station_id": other_station.id,
            "section_id": "",
            **csrf_form_field(client),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(product)
    assert product.name_de == "Krautsalat (neu)"
    assert product.name_en == "Coleslaw"
    assert product.station_id == other_station.id


def test_15_admin_can_deactivate_product(client, db_session):
    station = make_station(db_session)
    product = PreparedProduct(name_de="Krautsalat", station_id=station.id)
    db_session.add(product)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/products/{product.id}/deactivate", data=csrf_form_field(client), follow_redirects=False
    )
    assert response.status_code == 303
    db_session.refresh(product)
    assert product.is_active is False


def test_16_inactive_product_cannot_receive_new_preparation_task(client, db_session):
    station = make_station(db_session)
    product = PreparedProduct(name_de="Krautsalat", station_id=station.id)
    db_session.add(product)
    db_session.commit()
    _login_admin(client, db_session)
    client.post(f"/admin/products/{product.id}/deactivate", data=csrf_form_field(client))

    response = client.post(f"/products/{product.id}/prepare-tomorrow", headers={"X-CSRF-Token": client.cookies.get("csrf_token")})
    assert response.status_code == 400


def test_17_section_must_belong_to_selected_station(client, db_session):
    station_a = make_station(db_session, "PASS")
    station_b = make_station(db_session, "GRILL")
    section_of_a = Section(station_id=station_a.id, name="SALAT")
    db_session.add(section_of_a)
    db_session.commit()
    _login_admin(client, db_session)

    # section_of_a belongs to station_a, but we claim station_b here.
    response = client.post(
        "/admin/products",
        data={
            "name_de": "Krautsalat",
            "name_en": "",
            "station_id": station_b.id,
            "section_id": section_of_a.id,
            **csrf_form_field(client),
        },
    )
    assert response.status_code == 400
    assert db_session.query(PreparedProduct).filter_by(name_de="Krautsalat").first() is None
