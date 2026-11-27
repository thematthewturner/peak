from datetime import date, timedelta

from sqlalchemy import select

from peak.models import Attempt, Ticket
from tests.test_items_api import make_item


def post(student, item, key, answer, **extra):
    return student.post("/api/attempts", json={"item_id": item.id, "idempotency_key": key, "answer": answer, **extra}).json()


def test_miss_to_ticket_flow(clients, db):
    item = make_item(db, family_id="famA")
    _, student = clients
    r = post(student, item, "key-20001", "A", confidence="sure")
    d = student.post(f"/api/attempts/{r['attempt_id']}/diagnose", json={"cold_retry_correct": True}).json()
    assert d["ticket_required"] and d["cause"] == "execution"
    # 'careless' is never terminal: execution needs a named micro-skill
    bad = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "execution"})
    assert bad.status_code == 422 and "micro-skill" in bad.json()["detail"]
    t = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "execution", "micro_skill": "skips_plug_back"}).json()
    assert t["state"] == "OPEN" and t["cue"] == "Plug it back in"
    again = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "execution", "micro_skill": "skips_plug_back"}).json()
    assert again["id"] == t["id"]  # idempotent per origin attempt


def test_ticket_ownership(clients, db):
    item = make_item(db)
    parent, student = clients
    r = post(student, item, "key-20002", "A")
    t = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "content_gap"}).json()
    assert parent.get("/api/tickets").json() == []
    assert parent.post(f"/api/tickets/{t['id']}/repair/start", json={"intervention": "worked_example"}).status_code == 404


def test_full_ladder_through_api(clients, db):
    origin = make_item(db, source_ref="O", family_id="famA")
    fresh1 = make_item(db, source_ref="F1", family_id="famB")
    fresh2 = make_item(db, source_ref="F2", family_id="famC")
    same = make_item(db, source_ref="S", family_id="famA")
    _, student = clients
    r = post(student, origin, "key-30001", "A")
    t = student.post(f"/api/attempts/{r['attempt_id']}/ticket", json={"cause": "content_gap"}).json()
    assert student.post(f"/api/tickets/{t['id']}/repair/start", json={"intervention": "worked_example"}).json()["state"] == "REPAIRING"
    assert student.post(f"/api/tickets/{t['id']}/repair/complete").json()["state"] == "RETRY_DUE"

    def state():
        return db.get(Ticket, t["id"]).state

    # Same day as the repair never counts, same-family never counts.
    post(student, fresh1, "key-30002", "B")
    db.expire_all()
    assert state() == "RETRY_DUE"
    # Move the repair into the past so later attempts count.
    row = db.get(Ticket, t["id"])
    row.repaired_at = (date.today() - timedelta(days=8)).isoformat()
    db.commit()
    post(student, same, "key-30003", "B")
    db.expire_all()
    assert state() == "RETRY_DUE"
    post(student, fresh2, "key-30004", "B", flags={"mixed_unlabeled": True})
    db.expire_all()
    assert state() == "TRANSFER_DUE"
    assert len(db.scalars(select(Attempt)).all()) == 4
