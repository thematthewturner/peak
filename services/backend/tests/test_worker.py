from datetime import datetime, timedelta, timezone

from peak import ops_report, worker
from peak.db import Heartbeat, Job, Login, User, now


def test_drain_blocks_work_and_clear_resets(db):
    worker.HANDLERS["t"] = lambda: True
    try:
        assert worker.work_once() is True
        ops_report.request_drain(db)
        assert worker.draining() and worker.work_once() is False
        worker.clear_drain()
        assert not worker.draining() and worker.work_once() is True
    finally:
        worker.HANDLERS.pop("t")


def test_housekeeping_deletes_only_expired_logins(db):
    db.add(User(id="u1", username="u", password_hash="x", role="student"))
    db.commit()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    db.add_all([Login(token_hash="a", user_id="u1", csrf="c", expires=past), Login(token_hash="b", user_id="u1", csrf="c", expires=future)])
    db.commit()
    assert worker.housekeeping() == 1
    db.expire_all()
    assert db.get(Login, "b") and not db.get(Login, "a")


def test_readiness_reflects_worker_heartbeat(clients, db):
    parent, _ = clients
    assert parent.get("/api/readiness").status_code == 503
    db.add(Heartbeat(id="worker", at=now()))
    db.commit()
    assert parent.get("/api/readiness").json()["status"] == "ok"


def test_ops_report_counts_running_jobs(db):
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    db.add_all([Job(ref_id="a", kind="k", state="running", lease_until=future), Job(ref_id="b", kind="k", state="pending")])
    db.commit()
    assert ops_report.running_jobs(db) == 1
