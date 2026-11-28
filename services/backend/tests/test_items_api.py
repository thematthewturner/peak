import json

from peak.models import Item, Session
from peak.seed import seed_skills


def make_item(db, **kw):
    seed_skills(db)
    base = dict(
        origin="official", source_ref="Q1", skill_id="algebra.linear-equations-in-one-variable", difficulty="medium",
        format="mc", status="verified",
        content=json.dumps({"stem": "2x = 6. x = ?", "choices": {"A": "2", "B": "3", "C": "4", "D": "5"}}),
        key=json.dumps(["B"]), rationale="Divide both sides by 2.",
    )
    base.update(kw)
    item = Item(**base)
    db.add(item)
    db.commit()
    return item


def test_item_payload_never_contains_key_or_rationale(clients, db):
    item = make_item(db)
    _, student = clients
    body = student.get(f"/api/items/{item.id}").json()
    text = json.dumps(body)
    assert "rationale" not in text and "Divide both sides" not in text and '"key"' not in text
    assert body["stem"].startswith("2x")


def test_attempt_then_review_reveals(clients, db):
    item = make_item(db)
    _, student = clients
    r = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00001", "answer": "B", "confidence": "sure"})
    assert r.status_code == 200 and r.json()["correct"] is True and r.json()["rationale"].startswith("Divide")
    assert student.get(f"/api/attempts/{r.json()['attempt_id']}/review").json()["revealed"] is True


def test_idempotent_submit_does_not_duplicate(clients, db):
    item = make_item(db)
    _, student = clients
    body = {"item_id": item.id, "idempotency_key": "key-00002", "answer": "A"}
    first = student.post("/api/attempts", json=body).json()
    second = student.post("/api/attempts", json=body).json()
    assert first["attempt_id"] == second["attempt_id"] and second["created"] is False
    assert len(student.get("/api/attempts").json()) == 1


def test_first_exposure_tracked(clients, db):
    from sqlalchemy import select
    from peak.models import Attempt
    item = make_item(db)
    _, student = clients
    for i in range(2):
        student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": f"key-1000{i}", "answer": "B"})
    flags = [a.first_exposure for a in db.scalars(select(Attempt).order_by(Attempt.created))]
    assert flags == [True, False]


def test_timed_mode_never_reveals(clients, db):
    item = make_item(db)
    parent, student = clients
    me = student.get("/api/me").json()
    s = Session(user_id=me["id"], purpose="timed", mode="timed")
    db.add(s)
    db.commit()
    r = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00003", "answer": "B", "session_id": s.id}).json()
    assert r["revealed"] is False and "rationale" not in r and "key" not in r


def test_benchmark_locked_and_unverified_not_served(clients, db):
    locked = make_item(db, source_ref="Q2", benchmark_locked=True)
    draft = make_item(db, source_ref="Q3", status="draft")
    _, student = clients
    assert student.get(f"/api/items/{locked.id}").status_code == 404
    assert student.get(f"/api/items/{draft.id}").status_code == 404
    r = student.post("/api/attempts", json={"item_id": locked.id, "idempotency_key": "key-00004", "answer": "B"})
    assert r.status_code == 404


def test_numeric_entry_rejected_with_reason(clients, db):
    item = make_item(db, source_ref="Q4", format="numeric", key=json.dumps(["3/2"]), content=json.dumps({"stem": "x?"}))
    _, student = clients
    r = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00005", "answer": "1 1/2"})
    assert r.status_code == 422 and "Mixed" in r.json()["detail"]
    ok = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00006", "answer": "1.5"}).json()
    assert ok["correct"] is True


def test_other_users_attempt_is_404(clients, db):
    item = make_item(db)
    parent, student = clients
    aid = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00007", "answer": "B"}).json()["attempt_id"]
    assert parent.get(f"/api/attempts/{aid}/review").status_code == 404


def test_skip_counts_as_wrong(clients, db):
    item = make_item(db)
    _, student = clients
    r = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-00008"}).json()
    assert r["correct"] is False


def test_requires_login(db):
    from fastapi.testclient import TestClient
    from peak.api import app
    with TestClient(app) as anon:
        assert anon.get("/api/items/x").status_code == 401


def test_miss_withholds_solution_until_cold_retry(clients, db):
    item = make_item(db, source_ref="CR1")
    _, student = clients
    first = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-50001", "answer": "A"}).json()
    assert first["revealed"] is False and first["needs_cold_retry"] is True
    assert "rationale" not in first and "key" not in first
    assert student.get(f"/api/attempts/{first['attempt_id']}/review").json()["revealed"] is False
    retry = student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": "key-50002", "answer": "B"}).json()
    assert retry["revealed"] is True and retry["key"] == ["B"]
    assert student.get(f"/api/attempts/{first['attempt_id']}/review").json()["revealed"] is True


def test_next_item_serves_only_fresh_verified_unlocked(clients, db):
    a = make_item(db, source_ref="N1")
    make_item(db, source_ref="N2", benchmark_locked=True)
    make_item(db, source_ref="N3", status="review")
    _, student = clients
    assert student.get("/api/items/next").json()["id"] == a.id
    student.post("/api/attempts", json={"item_id": a.id, "idempotency_key": "key-50003", "answer": "B"})
    r = student.get("/api/items/next")
    assert r.status_code == 404 and "new item" in r.json()["detail"]
    assert student.get("/api/items/next?skill_id=nope").status_code == 404


def test_taxonomy_endpoint(clients):
    _, student = clients
    body = student.get("/api/taxonomy").json()
    assert "execution" in body["causes"] and any(m["key"] == "skips_plug_back" for m in body["micro_skills"])


def test_skills_names_for_the_ui(clients, db):
    from peak.seed import seed_skills
    seed_skills(db)
    _, student = clients
    body = student.get("/api/skills").json()
    assert body["advanced_math.nonlinear-functions"] == {"name": "Nonlinear functions", "domain": "advanced_math", "section": "math"}
    assert not any(k.startswith("micro.") for k in body)
