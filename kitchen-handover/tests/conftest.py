import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
import app.models  # noqa: F401  (populates Base.metadata)

# Import order matters here: `import app.models` binds the name `app` to the
# top-level package. This import must come after, so `app` ends up bound to
# the FastAPI instance, not the package module.
from app.main import app


@pytest.fixture()
def engine():
    """A fresh in-memory SQLite database per test.

    StaticPool + check_same_thread=False so the single in-memory database is
    shared across connections within this engine (otherwise every connection
    would see its own empty :memory: database).
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not enforce foreign keys unless told to, per connection.
    @event.listens_for(eng, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Session:
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine: Engine) -> TestClient:
    """An HTTP client wired to the SAME in-memory database as db_session, so
    a test can create rows directly with db_session and then hit real routes
    with this client and see that data (or vice versa)."""
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
