import os
import tempfile

os.environ["SECRET_KEY"] = "test-only-secret-key-at-least-32-characters"
os.environ["YOUTUBE_DOWNLOAD_ENABLED"] = "false"
os.environ["YOUTUBE_API_KEY"] = ""
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["STORAGE_ROOT"] = tempfile.mkdtemp(prefix="reclipd-test-")
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.db import Base, get_db
from app.main import app
from app import main


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(main, "auth_rate_limit", lambda r: None)
    monkeypatch.setattr(main, "enqueue_project", lambda db, p: None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def signed(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Creator",
            "email": "creator@example.com",
            "password": "secure-test-password",
        },
    )
    assert response.status_code == 201
    return client
