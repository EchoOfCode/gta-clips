import os
import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app, check_ready_dependencies

# In-memory SQLite for high-speed, isolated unit testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        app_name="GTA Clip Engine Test",
        environment="test",
        database_url=TEST_DATABASE_URL,
        internal_api_key="test-secret-key-12345",
        youtube_api_key="test-yt-key",
        twitch_client_id="test-twitch-id",
        twitch_client_secret="test-twitch-secret",
        log_json=False,
    )


@pytest.fixture(autouse=True)
def init_db() -> Generator[None, None, None]:
    """Create all database tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Yields a database session with automatic cleanup."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(
    db_session: Session, test_settings: Settings
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database and settings dependencies."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _override_get_settings
    app.dependency_overrides[check_ready_dependencies] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
