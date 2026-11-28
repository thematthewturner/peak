import json
from datetime import date, timedelta

from sqlalchemy import select

from peak import session_plan
from peak.models import Attempt, Card, Item, Ticket
from peak.seed import seed_skills
from peak.taxonomy import OFFICIAL_SKILLS, skill_id

MATH = ["algebra", "advanced_math", "problem_solving_data_analysis", "geometry_trigonometry"]
RW = ["craft_and_structure", "information_and_ideas", "standard_english_conventions", "expression_of_ideas"]


def bank(db, per_skill=6):
    """Original placeholder items across every skill, each in its own family pair."""
    seed_skills(db)
    n = 0
    for dom in MATH + RW:
        for name in OFFICIAL_SKILLS[dom]:
            sid = skill_id(dom, name)
            for i in range(per_skill):
                n += 1
                db.add(Item(origin="official", source_ref=f"T{n}", skill_id=sid, family_id=f"fam-{sid}-{i // 2}",
                            difficulty=["easy", "medium", "hard"][i % 3], format="mc", status="verified",
                            content=json.dumps({"stem": f"<p>Question {n}</p>", "choices": {"A": "1", "B": "2", "C": "3", "D": "4"}}),
                            key='["B"]', rationale=f"<p>Because {n}</p>"))
    db.commit()


def user_id(clients):
    return clients[1].get("/api/me").json()["id"]


def test_first_session_is_math_with_worked_examples_then_a_mixed_set(clients, db):
    bank(db)
    _, student = clients
    plan = student.post("/api/sessions/start", json={"minutes": 45}).json()
    kinds = [s["kind"] for s in plan["steps"]]
    assert plan["section"] == "math"
    assert kinds.count("worked") == 2  # new math skill: study solved ones first (guide s4.4)
    assert [s["block"] for s in plan["steps"] if s["kind"] == "worked"] == ["learn", "learn"]
    mixed = [s for s in plan["steps"] if s["block"] == "mixed"]
    assert len(mixed) >= 8
    assert len({s["item_id"] for s in plan["steps"] if "item_id" in s}) == sum(1 for s in plan["steps"] if "item_id" in s)
    doms = [s["domain"] for s in mixed]
    assert all(a != b for a, b in zip(doms, doms[1:])), doms  # interleaved: no domain twice in a row
    assert all(s["domain"] in MATH for s in mixed)  # mixed within one section
    assert {b["key"] for b in plan["blocks"]} >= {"learn", "mixed"} and all(b["why"] for b in plan["blocks"])


def test_no_worked_examples_once_the_skill_is_familiar(clients, db):
    bank(db)
    uid = user_id(clients)
    plan0 = session_plan.build(db, uid, 45, date.today(), seed=1)
    focus = plan0["focus_skill"]
    for item in db.scalars(select(Item).where(Item.skill_id == focus)).all()[:3]:
        db.add(Attempt(user_id=uid, item_id=item.id, answer="A", correct=False, idempotency_key=f"k-{item.id}"))
    db.commit()
    plan = session_plan.build(db, uid, 45, date.today(), seed=1)
    if plan["focus_skill"] == focus:
        assert not any(s["kind"] == "worked" and s["skill_id"] == focus for s in plan["steps"])


def make_ticket(db, uid, state, due):
    item = db.scalars(select(Item).where(Item.skill_id == skill_id("algebra", "Linear functions"))).first()
    a = Attempt(user_id=uid, item_id=item.id, answer="A", correct=False, idempotency_key=f"o-{state}")
    db.add(a)
    db.flush()
    t = Ticket(user_id=uid, skill_id=item.skill_id, origin_attempt_id=a.id, cause="execution", micro_skill="sign_slips",
               state=state, repaired_at=(date.today() - timedelta(days=8)).isoformat(), next_due=due.isoformat(),
               rule="Plug it back in")
    db.add(t)
    db.commit()
    return t, item


def test_due_retry_comes_first_as_reattempt_plus_fresh_proof(clients, db):
    bank(db)
    uid = user_id(clients)
    t, origin = make_ticket(db, uid, "RETRY_DUE", date.today())
    plan = session_plan.build(db, uid, 45, date.today(), seed=2)
    first, second = plan["steps"][0], plan["steps"][1]
    assert first["kind"] == "reattempt" and first["item_id"] == origin.id and first["ticket_id"] == t.id
    assert second["kind"] == "question" and second["ticket_id"] == t.id and second["item_id"] != origin.id
    proof = db.get(Item, second["item_id"])
    assert proof.skill_id == origin.skill_id and proof.family_id != origin.family_id
    assert "Plug it back in" in second["reason"]


def test_one_week_proof_hides_unlabeled_in_the_mixed_set(clients, db):
    bank(db)
    uid = user_id(clients)
    t, _ = make_ticket(db, uid, "TRANSFER_DUE", date.today())
    plan = session_plan.build(db, uid, 45, date.today(), seed=3)
    proofs = [s for s in plan["steps"] if s.get("ticket_id") == t.id]
    assert len(proofs) == 1 and proofs[0]["block"] == "mixed" and proofs[0]["flags"] == {"mixed_unlabeled": True}


def test_five_minute_session_is_cards_only(clients, db):
    bank(db)
    _, student = clients
    plan = student.post("/api/sessions/start", json={"minutes": 5}).json()
    assert [s["kind"] for s in plan["steps"]] == ["cards"]
    assert student.post("/api/sessions/start", json={"minutes": 20}).status_code == 422


def test_worked_example_reveals_after_recording_and_never_comes_back_fresh(clients, db):
    bank(db)
    _, student = clients
    plan = student.post("/api/sessions/start", json={"minutes": 45}).json()
    w = next(s for s in plan["steps"] if s["kind"] == "worked")
    body = student.post(f"/api/items/{w['item_id']}/study", json={"idempotency_key": "study-0001", "session_id": plan["id"]}).json()
    assert body["key"] == ["B"] and body["rationale"].startswith("<p>Because")
    again = student.post(f"/api/items/{w['item_id']}/study", json={"idempotency_key": "study-0001", "session_id": plan["id"]})
    assert again.status_code == 200
    rows = db.scalars(select(Attempt).where(Attempt.item_id == w["item_id"])).all()
    assert len(rows) == 1 and rows[0].correct is None  # idempotent, and never scored
    assert student.get("/api/stats").json()["calibration"]["sure"] == 0
    nxt = student.post("/api/sessions/start", json={"minutes": 45}).json()
    assert w["item_id"] not in {s.get("item_id") for s in nxt["steps"]}


def test_summary_stats_and_rule_card(clients, db):
    bank(db)
    _, student = clients
    plan = student.post("/api/sessions/start", json={"minutes": 45}).json()
    qs = [s for s in plan["steps"] if s["kind"] == "question"][:3]
    ans = ["B", "A", "C"]
    conf = ["sure", "sure", "guess"]
    ids = []
    for i, (s, a, c) in enumerate(zip(qs, ans, conf)):
        r = student.post("/api/attempts", json={"item_id": s["item_id"], "idempotency_key": f"sum-000{i}", "answer": a,
                                                 "confidence": c, "session_id": plan["id"], "flags": s["flags"]}).json()
        ids.append(r["attempt_id"])
    t = student.post(f"/api/attempts/{ids[1]}/ticket", json={"cause": "execution", "micro_skill": "skips_plug_back",
                                                             "rule": "Plug the answer back into the original equation"}).json()
    assert t["rule"].startswith("Plug the answer")
    card = db.scalar(select(Card).where(Card.kind == "your rule"))
    assert card and card.back == "Plug the answer back into the original equation"
    summ = student.get(f"/api/sessions/{plan['id']}/summary").json()
    assert summ["answered"] == 3 and summ["correct"] == 1 and summ["sure_wrong"] == 1
    assert summ["fixes"][0]["rule"].startswith("Plug the answer")
    st = student.get("/api/stats").json()
    assert st["calibration"] == {"sure": 2, "sure_right": 1, "sure_wrong": 1} and st["week_sessions"] == 1
    assert sum(d["attempts"] for d in st["domains"].values()) == 3


def test_sessions_are_private(clients, db):
    bank(db)
    parent, student = clients
    sid = student.post("/api/sessions/start", json={"minutes": 25}).json()["id"]
    assert parent.get(f"/api/sessions/{sid}").status_code == 404
    assert parent.get(f"/api/sessions/{sid}/summary").status_code == 404


def test_interleave_separates_domains_whenever_possible():
    import random
    steps = [{"domain": d, "i": i} for i, d in enumerate("aaaabbbcc")]
    for seed in range(20):
        out = session_plan.interleave(steps, random.Random(seed))
        doms = [s["domain"] for s in out]
        assert sorted(doms) == sorted("aaaabbbcc") and all(x != y for x, y in zip(doms, doms[1:]))


def test_preview_describes_today_without_saving(clients, db):
    from peak.models import Session
    bank(db)
    _, student = clients
    p = student.get("/api/sessions/preview?minutes=45").json()
    assert p["focus_skill"] and p["focus_reason"] and p["questions"] >= 10 and p["section"] == "math"
    assert "hasn't seen you try it yet" in p["focus_reason"]
    assert db.scalar(select(Session)) is None and db.scalar(select(Attempt)) is None


def test_focus_reason_names_the_last_pattern(clients, db):
    bank(db)
    uid = user_id(clients)
    t, origin = make_ticket(db, uid, "OPEN", date.today() + timedelta(days=5))
    plan = session_plan.build(db, uid, 45, date.today(), only_skill=origin.skill_id)
    assert plan["focus_reason"] == "Last time, sign slips when factoring tripped you up. Try it again in new problems."


def test_just_this_skill_stays_on_one_skill(clients, db):
    bank(db)
    _, student = clients
    sid = skill_id("geometry_trigonometry", "Circles")
    plan = student.post("/api/sessions/start", json={"minutes": 25, "only_skill": sid}).json()
    qs = [s for s in plan["steps"] if s.get("item_id")]
    assert qs and all(s["skill_id"] == sid for s in qs)
    assert student.post("/api/sessions/start", json={"minutes": 25, "section": "rw"}).json()["section"] == "rw"


def test_active_session_offers_resume_until_done(clients, db):
    bank(db)
    _, student = clients
    assert student.get("/api/sessions/active").json() is None
    plan = student.post("/api/sessions/start", json={"minutes": 15}).json()
    q = next(s for s in plan["steps"] if s["kind"] == "question")
    student.post("/api/attempts", json={"item_id": q["item_id"], "idempotency_key": "res-0001", "answer": "B",
                                         "confidence": "sure", "session_id": plan["id"]})
    act = student.get("/api/sessions/active").json()
    assert act["id"] == plan["id"] and act["left"] == act["total"] - 1
    student.post(f"/api/sessions/{plan['id']}/end", json={"usefulness": 4})
    assert student.get("/api/sessions/active").json() is None


def test_show_example_is_a_solved_same_skill_question(clients, db):
    bank(db)
    _, student = clients
    sid = skill_id("algebra", "Linear functions")
    ex = student.post(f"/api/skills/{sid}/example", json={"idempotency_key": "ex-00001"}).json()
    assert ex["skill_id"] == sid and ex["key"] == ["B"] and ex["rationale"]
    again = student.post(f"/api/skills/{sid}/example", json={"idempotency_key": "ex-00001"}).json()
    assert again["id"] == ex["id"]  # idempotent: the same example, one recorded study


def test_seen_before_is_labeled_and_never_first_exposure(clients, db):
    bank(db, per_skill=1)
    _, student = clients
    sid = skill_id("geometry_trigonometry", "Circles")
    item = student.get(f"/api/items/next?skill_id={sid}").json()
    assert item["seen_before"] is False
    student.post("/api/attempts", json={"item_id": item["id"], "idempotency_key": "seen-001", "answer": "A"})
    assert student.get(f"/api/items/next?skill_id={sid}").status_code == 404
    again = student.get(f"/api/items/next?skill_id={sid}&allow_seen=true").json()
    assert again["id"] == item["id"] and again["seen_before"] is True
    student.post("/api/attempts", json={"item_id": item["id"], "idempotency_key": "seen-002", "answer": "B"})
    firsts = [a.first_exposure for a in db.scalars(select(Attempt).where(Attempt.item_id == item["id"]).order_by(Attempt.created))]
    assert firsts == [True, False]
