"""Tests for the SQLAlchemy models themselves — relationships, uniqueness
constraints, the status CHECK constraint, the partial unique index that
guards against duplicate active preparation tasks, and foreign-key
enforcement.

Business rules (e.g. "return a friendly message instead of raising" for a
duplicate prepare-tomorrow tap) belong to the service layer, built in the
next step — these tests only confirm the data layer itself is correct.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models import (
    PreparationTask,
    PreparedProduct,
    ProductLocationHistory,
    Section,
    Station,
    StorageLocation,
    Worker,
)

TODAY = date(2026, 10, 4)
TOMORROW = TODAY + timedelta(days=1)
YESTERDAY = TODAY - timedelta(days=1)


def make_worker(db: Session, name: str = "Michael") -> Worker:
    # password_hash is a placeholder here, not a real Argon2 hash — these
    # are model/constraint tests, not auth tests (see test_auth.py for
    # real password hashing/verification coverage). Only NOT NULL +
    # "some string" matters at this layer.
    worker = Worker(display_name=name, email=f"{name.lower()}@example.test", password_hash="x")
    db.add(worker)
    db.commit()
    return worker


def make_station_with_section(db: Session) -> tuple[Station, Section]:
    station = Station(name="PASS")
    db.add(station)
    db.commit()
    section = Section(station_id=station.id, name="SALAT")
    db.add(section)
    db.commit()
    return station, section


def make_product(db: Session, station: Station, section: Section | None = None) -> PreparedProduct:
    product = PreparedProduct(name_de="Krautsalat", station_id=station.id, section_id=section.id if section else None)
    db.add(product)
    db.commit()
    return product


# ---------------------------------------------------------------------------
# Basic creation + relationships
# ---------------------------------------------------------------------------


def test_station_section_product_relationships(db_session: Session):
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)

    db_session.refresh(station)
    db_session.refresh(section)

    assert station.sections == [section]
    assert station.products == [product]
    assert section.products == [product]
    assert product.station.name == "PASS"
    assert product.section.name == "SALAT"


def test_product_without_section_is_allowed(db_session: Session):
    """GRILL/FRITTEUSE/DESSERT currently have no sub-sections — a product
    must be able to belong to a station directly."""
    station = Station(name="GRILL")
    db_session.add(station)
    db_session.commit()

    product = PreparedProduct(name_de="Roastbeef", station_id=station.id, section_id=None)
    db_session.add(product)
    db_session.commit()

    assert product.section_id is None
    assert product.section is None


def test_prepared_product_name_en_is_optional(db_session: Session):
    station = Station(name="DESSERT")
    db_session.add(station)
    db_session.commit()

    product = PreparedProduct(name_de="Kaiserschmarrn", station_id=station.id)
    db_session.add(product)
    db_session.commit()

    assert product.name_en is None


# ---------------------------------------------------------------------------
# Uniqueness constraints
# ---------------------------------------------------------------------------


def test_station_name_must_be_unique(db_session: Session):
    db_session.add(Station(name="PASS"))
    db_session.commit()

    db_session.add(Station(name="PASS"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_section_name_unique_within_station_but_not_across_stations(db_session: Session):
    pass_station = Station(name="PASS")
    grill_station = Station(name="GRILL")
    db_session.add_all([pass_station, grill_station])
    db_session.commit()

    db_session.add(Section(station_id=pass_station.id, name="SAUCES"))
    db_session.commit()

    # Same name, different station -> allowed.
    db_session.add(Section(station_id=grill_station.id, name="SAUCES"))
    db_session.commit()

    # Same name, same station -> rejected.
    db_session.add(Section(station_id=pass_station.id, name="SAUCES"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_storage_location_name_must_be_unique(db_session: Session):
    db_session.add(StorageLocation(name="Kühlhaus 1"))
    db_session.commit()

    db_session.add(StorageLocation(name="Kühlhaus 1"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_worker_display_name_must_be_unique(db_session: Session):
    db_session.add(Worker(display_name="Michael", email="michael1@example.test", password_hash="x"))
    db_session.commit()

    db_session.add(Worker(display_name="Michael", email="michael2@example.test", password_hash="x"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_worker_email_must_be_unique(db_session: Session):
    db_session.add(Worker(display_name="Michael", email="same@example.test", password_hash="x"))
    db_session.commit()

    db_session.add(Worker(display_name="Someone Else", email="same@example.test", password_hash="x"))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# PreparationTask: status CHECK constraint
# ---------------------------------------------------------------------------


def test_task_status_check_constraint_rejects_invalid_value(db_session: Session):
    """The ORM's TaskStatus enum would never let us assign a bad value in
    Python, so this test bypasses the ORM with raw SQL to confirm the DB
    itself also refuses — defense in depth, not just application-level
    validation."""
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)
    worker = make_worker(db_session)
    db_session.commit()

    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO preparation_tasks "
                "(prepared_product_id, due_date, status, created_by_id, created_at) "
                "VALUES (:pid, :due, 'BOGUS_STATUS', :wid, CURRENT_TIMESTAMP)"
            ),
            {"pid": product.id, "due": TOMORROW.isoformat(), "wid": worker.id},
        )
        db_session.commit()


# ---------------------------------------------------------------------------
# PreparationTask: the duplicate-active-task guard
# ---------------------------------------------------------------------------


def test_duplicate_active_task_same_product_same_due_date_is_rejected(db_session: Session):
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)
    worker = make_worker(db_session)

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id))
    db_session.commit()

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_second_active_task_for_different_due_date_is_allowed(db_session: Session):
    """An overdue task from yesterday and a freshly created task for
    tomorrow are different due_date values, so both may exist at once
    (docs/mvp/kitchen-handover.md, resolved-ambiguity on dedup scope)."""
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)
    worker = make_worker(db_session)

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=YESTERDAY, created_by_id=worker.id))
    db_session.commit()

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id))
    db_session.commit()  # must not raise

    tasks = db_session.query(PreparationTask).filter_by(prepared_product_id=product.id).all()
    assert len(tasks) == 2


def test_new_active_task_allowed_for_same_due_date_once_old_one_is_completed(db_session: Session):
    """The partial unique index only applies to status='TO_PREPARE' rows, so
    completing the old task frees up that (product, due_date) pair."""
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)
    worker = make_worker(db_session)

    first = PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id)
    db_session.add(first)
    db_session.commit()

    first.status = TaskStatus.COMPLETED
    db_session.commit()

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=worker.id))
    db_session.commit()  # must not raise

    active = (
        db_session.query(PreparationTask)
        .filter_by(prepared_product_id=product.id, due_date=TOMORROW, status=TaskStatus.TO_PREPARE)
        .all()
    )
    assert len(active) == 1


# ---------------------------------------------------------------------------
# Foreign key enforcement
# ---------------------------------------------------------------------------


def test_product_cannot_reference_nonexistent_station(db_session: Session):
    db_session.add(PreparedProduct(name_de="Ghost Product", station_id=9999))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_task_cannot_reference_nonexistent_worker(db_session: Session):
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)

    db_session.add(PreparationTask(prepared_product_id=product.id, due_date=TOMORROW, created_by_id=9999))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Location + history
# ---------------------------------------------------------------------------


def test_changing_current_location_and_appending_history(db_session: Session):
    """This is the data-layer shape the ProductLocationService (next step)
    will drive transactionally: update current_location_id AND append a
    history row."""
    station, section = make_station_with_section(db_session)
    product = make_product(db_session, station, section)
    worker = make_worker(db_session)
    location_a = StorageLocation(name="Kühlschrank 2")
    location_b = StorageLocation(name="Kühlhaus 1")
    db_session.add_all([location_a, location_b])
    db_session.commit()

    product.current_location_id = location_a.id
    db_session.add(ProductLocationHistory(prepared_product_id=product.id, storage_location_id=location_a.id, recorded_by_id=worker.id))
    db_session.commit()

    product.current_location_id = location_b.id
    db_session.add(ProductLocationHistory(prepared_product_id=product.id, storage_location_id=location_b.id, recorded_by_id=worker.id))
    db_session.commit()

    db_session.refresh(product)
    assert product.current_location_id == location_b.id
    assert len(product.location_history) == 2
    # Most recent first (model's relationship order_by).
    assert product.location_history[0].storage_location_id == location_b.id
    assert product.location_history[1].storage_location_id == location_a.id
