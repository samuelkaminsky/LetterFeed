import os

os.environ["LETTERFEED_DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LETTERFEED_SECRET_KEY"] = "testsecret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, engine, get_db
from app.main import app

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown_db():
    """Set up and tear down the database for each test.

    This fixture is automatically used for all tests. It creates all tables
    before a test and drops them afterwards. This ensures a clean database for
    every test.
    """
    from app.crud.entries import _latest_timestamp_cache
    from app.crud.feed_cache import _feed_memory_cache

    _feed_memory_cache.clear()
    _latest_timestamp_cache.clear()

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

    _feed_memory_cache.clear()
    _latest_timestamp_cache.clear()


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Yield a database session for a test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture(db_session):
    """Yield a TestClient for a test."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db(request):
    """Clean up the test database after the test session.

    This fixture is automatically used once per test session. It registers a
    finalizer to remove the test database file after all tests have run.
    """

    def remove_test_db():
        # The path is relative to the backend directory where pytest is run
        db_file = "test.db"
        if os.path.exists(db_file):
            os.remove(db_file)

    request.addfinalizer(remove_test_db)
