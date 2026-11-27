import json
from datetime import date, timedelta

from peak.models import Card, Ticket
from tests.test_items_api import make_item


def test_today_default_and_validation(clients, db):
    make_item(db)
    _, student = clients
    body = student.get("/api/today?minutes=25").json()
    kinds = [b["kind"] for b in body["blocks"]]
    assert "focus" in kinds and "mixed" in kinds
    assert all(b["reason"] for b in body["blocks"])
    assert student.get("/api/today?minutes=20").status_code == 422


def test_today_counts_due_verifications_and_school_throttle(clients, db):
    item = make_item(db)
    _, student = clients
    r = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-40001", "answer": "A"}).json()
    t = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "content_gap"}).json()
    row = db.get(Ticket, t["id"])
    row.state, row.next_due = "RETRY_DUE", date.today().isoformat()
    db.commit()
    kinds = {b["kind"] for b in student.get("/api/today?minutes=25").json()["blocks"]}
    assert "verification" in kinds
    student.post("/api/school-tests", json={"title": "Alg 2 test", "on_date": (date.today() + timedelta(days=2)).isoformat()})
    throttled = student.get("/api/today?minutes=40").json()
    assert throttled["throttled"] and throttled["minutes"] == 5 and throttled["deferred_verifications"] == 1


def test_cards_seed_review_and_schedule(clients, db):
    _, student = clients
    due = student.get("/api/cards/due").json()
    assert len(due) >= 20
    cid = due[0]["id"]
    r = student.post(f"/api/cards/{cid}/review", json={"correct": True, "confidence": "sure", "elapsed_ms": 1000}).json()
    assert r["rating"] == 4
    assert cid not in [c["id"] for c in student.get("/api/cards/due").json()]
    assert db.get(Card, cid).due > date.today().isoformat()


def test_card_ownership(clients, db):
    parent, student = clients
    cid = student.get("/api/cards/due").json()[0]["id"]
    assert parent.post(f"/api/cards/{cid}/review", json={"correct": True}).status_code == 404


def test_benchmark_series_separation(clients):
    _, student = clients
    clean = student.post("/api/benchmarks", json={"source": "bluebook", "taken_on": "2026-12-20", "rw_score": 640, "math_score": 520,
                                                  "unseen": True, "single_sitting": True, "uninterrupted": True, "unaided": True}).json()
    dirty = student.post("/api/benchmarks", json={"source": "bluebook", "taken_on": "2027-01-10", "rw_score": 660, "math_score": 560,
                                                  "unseen": True, "single_sitting": True, "uninterrupted": False, "unaided": True}).json()
    assert clean["clean"] and clean["total"] == 1160 and not dirty["clean"]
    series = student.get("/api/benchmarks").json()
    assert len(series["bluebook_clean"]) == 1 and len(series["bluebook_exposed"]) == 1
    assert student.post("/api/benchmarks", json={"source": "psat", "taken_on": "bad"}).status_code == 422


def test_event_batches_are_idempotent(clients):
    _, student = clients
    sid = student.post("/api/sessions", json={"purpose": "timed", "mode": "timed", "minutes": 40}).json()["id"]
    batch = {"events": [{"seq": 1, "kind": "view", "data": {}}, {"seq": 2, "kind": "answer", "data": {"x": 1}}]}
    assert student.post(f"/api/sessions/{sid}/events", json=batch).json() == {"stored": 2, "duplicates": 0}
    again = student.post(f"/api/sessions/{sid}/events", json={"events": batch["events"] + [{"seq": 3, "kind": "end"}]}).json()
    assert again == {"stored": 1, "duplicates": 2}


def test_session_ownership(clients):
    parent, student = clients
    sid = student.post("/api/sessions", json={"purpose": "drill"}).json()["id"]
    assert parent.post(f"/api/sessions/{sid}/end", json={"usefulness": 4}).status_code == 404
    assert student.post(f"/api/sessions/{sid}/end", json={"usefulness": 4}).status_code == 200
    assert json.dumps(student.get("/api/benchmarks").json())
