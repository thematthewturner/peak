import os
import tempfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="peak-tests-"))
os.environ["DATABASE_URL"] = os.getenv("PEAK_TEST_DATABASE_URL", f"sqlite:///{ROOT}/test.db")
os.environ["DATA_DIR"] = str(ROOT / "files")
os.environ["PEAK_DEMO"] = "1"
os.environ["APP_BASE_URL"] = "http://localhost:3000"

import pytest
from fastapi.testclient import TestClient

from peak import models  # noqa: F401
from peak.api import app
from peak.db import Base, SessionLocal, engine

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def clients(db):
    with TestClient(app) as parent, TestClient(app) as student:
        for client, role in ((parent, "parent"), (student, "student")):
            response = client.post(
                "/api/login", json={"username": role, "password": f"peak-{role}-demo"}, headers=ORIGIN
            )
            assert response.status_code == 200, response.text
            client.headers.update({**ORIGIN, "X-CSRF-Token": response.json()["csrf"]})
        yield parent, student
