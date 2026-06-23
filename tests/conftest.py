import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.state.db import Base, get_db
from src.state.models import SessionModel, StepModel, ArtifactModel
from src.api.main import app

from sqlalchemy.pool import StaticPool

# Create in-memory database for isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session")
def fixture_db_session():
    """Fixture providing an isolated in-memory SQLAlchemy session."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def fixture_client(db_session):
    """Fixture providing a FastAPI TestClient with database overrides."""
    from fastapi.testclient import TestClient

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
