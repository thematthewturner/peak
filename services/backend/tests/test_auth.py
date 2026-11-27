from fastapi.testclient import TestClient

from peak.api import app
from tests.conftest import ORIGIN


def test_health_and_me(clients):
    parent, student = clients
    assert parent.get("/api/health").json() == {"status": "ok"}
    assert parent.get("/api/me").json()["role"] == "parent"
    assert student.get("/api/me").json()["role"] == "student"


def test_unauthenticated_me_is_401(db):
    with TestClient(app) as anon:
        assert anon.get("/api/me").status_code == 401


def test_mutation_needs_matching_origin(clients):
    parent, _ = clients
    r = parent.post("/api/logout", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_mutation_needs_csrf(clients):
    parent, _ = clients
    parent.headers.pop("X-CSRF-Token")
    assert parent.post("/api/logout").status_code == 403


def test_bad_login_throttles(db):
    with TestClient(app) as anon:
        codes = [
            anon.post("/api/login", json={"username": "parent", "password": "wrong"}, headers=ORIGIN).status_code
            for _ in range(10)
        ]
    assert codes[0] == 401 and codes[-1] == 429


def test_logout_invalidates_session(clients):
    parent, _ = clients
    assert parent.post("/api/logout").status_code == 200
    assert parent.get("/api/me").status_code == 401
