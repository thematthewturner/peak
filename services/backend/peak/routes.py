"""Item and attempt routes. Every route enforces ownership via the authenticated user."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import items as svc
from .auth import authenticate
from .db import get_db
from .models import Attempt, Item, Session

router = APIRouter(prefix="/api")


def _item(db, item_id):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@router.get("/items/{item_id}")
def get_item(item_id: str, user=Depends(authenticate), db=Depends(get_db)):
    item = _item(db, item_id)
    if not svc.servable(item, purpose="drill"):
        raise HTTPException(404, "Item not found")
    return svc.student_safe(item)


class AttemptIn(BaseModel):
    item_id: str
    idempotency_key: str = Field(min_length=8, max_length=80)
    answer: str | None = Field(default=None, max_length=40)
    session_id: str | None = None
    confidence: str | None = None
    elapsed_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    flags: dict = Field(default_factory=dict)


@router.post("/attempts")
def create_attempt(body: AttemptIn, user=Depends(authenticate), db=Depends(get_db)):
    item = _item(db, body.item_id)
    session = None
    if body.session_id:
        session = db.get(Session, body.session_id)
        if not session or session.user_id != user.id:
            raise HTTPException(404, "Session not found")
    try:
        attempt, created = svc.record_attempt(
            db, user_id=user.id, item=item, idempotency_key=body.idempotency_key, answer=body.answer,
            session_id=body.session_id, confidence=body.confidence, elapsed_ms=body.elapsed_ms, flags=body.flags,
        )
    except svc.AttemptError as error:
        raise HTTPException(error.status, str(error)) from None
    timed = bool(session and session.mode == "timed")
    if created:
        from . import ticket_service  # evidence for any awaiting ticket on this skill
        ticket_service.apply_attempt(db, attempt, item)
    return {"created": created, **svc.review(db, attempt, item, timed=timed)}


@router.get("/attempts/{attempt_id}/review")
def attempt_review(attempt_id: str, user=Depends(authenticate), db=Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:  # ownership: never reveal that it exists
        raise HTTPException(404, "Attempt not found")
    session = db.get(Session, attempt.session_id) if attempt.session_id else None
    return svc.review(db, attempt, db.get(Item, attempt.item_id), timed=bool(session and session.mode == "timed"))


@router.get("/attempts")
def list_attempts(user=Depends(authenticate), db=Depends(get_db), limit: int = 50):
    rows = db.scalars(
        select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.created.desc()).limit(min(limit, 200))
    ).all()
    return [
        {"id": a.id, "item_id": a.item_id, "correct": a.correct, "confidence": a.confidence,
         "elapsed_ms": a.elapsed_ms, "created": a.created}
        for a in rows
    ]


# ---- review, tickets ------------------------------------------------------------------------
from datetime import date  # noqa: E402

from . import ticket_service as tsvc  # noqa: E402
from .models import Ticket  # noqa: E402
from .taxonomy import Cause  # noqa: E402


class DiagnoseIn(BaseModel):
    cold_retry_correct: bool | None = None
    requested_quantity_flag: bool = False


@router.post("/attempts/{attempt_id}/diagnose")
def diagnose_attempt(attempt_id: str, body: DiagnoseIn, user=Depends(authenticate), db=Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    d = tsvc.propose(db, attempt, db.get(Item, attempt.item_id), cold_retry_correct=body.cold_retry_correct,
                     requested_quantity_flag=body.requested_quantity_flag)
    db.commit()
    return {"kind": d.kind, "cause": d.cause.value if d.cause else None, "ticket_required": d.ticket_required,
            "mastery_credit": d.mastery_credit, "reverify_days": list(d.reverify_days), "reasons": list(d.reasons)}


class TicketIn(BaseModel):
    cause: str
    micro_skill: str | None = None


@router.post("/attempts/{attempt_id}/ticket")
def create_ticket(attempt_id: str, body: TicketIn, user=Depends(authenticate), db=Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    try:
        cause = Cause(body.cause)
        ticket = tsvc.open_ticket(db, attempt, db.get(Item, attempt.item_id), cause, body.micro_skill)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return _ticket(ticket)


def _ticket(t: Ticket) -> dict:
    return {"id": t.id, "skill_id": t.skill_id, "cause": t.cause, "micro_skill": t.micro_skill, "cue": t.cue,
            "state": t.state, "next_due": t.next_due, "reopen_reason": t.reopen_reason,
            "intervention": t.intervention}


def _own_ticket(db, user, ticket_id) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Ticket not found")
    return t


@router.get("/tickets")
def list_tickets(user=Depends(authenticate), db=Depends(get_db)):
    rows = db.scalars(select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.created.desc())).all()
    return [_ticket(t) for t in rows]


class RepairIn(BaseModel):
    intervention: str = Field(min_length=1, max_length=60)


@router.post("/tickets/{ticket_id}/repair/start")
def repair_start(ticket_id: str, body: RepairIn, user=Depends(authenticate), db=Depends(get_db)):
    t = _own_ticket(db, user, ticket_id)
    try:
        return _ticket(tsvc.start_repair(db, t, body.intervention))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/tickets/{ticket_id}/repair/complete")
def repair_complete(ticket_id: str, user=Depends(authenticate), db=Depends(get_db)):
    t = _own_ticket(db, user, ticket_id)
    try:
        return _ticket(tsvc.complete_repair(db, t, date.today()))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


# ---- sessions, today, cards, benchmarks, school tests ---------------------------------------
import json  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from sqlalchemy import func  # noqa: E402

from . import composer, priority, srs  # noqa: E402
from .benchmarks import Conditions, series_for  # noqa: E402
from .cards_seed import seed_cards  # noqa: E402
from .models import Benchmark, Card, CardReview, Event, Plan, SchoolTest, Skill  # noqa: E402


def _today() -> date:
    return datetime.now(timezone.utc).date()


class SessionIn(BaseModel):
    purpose: str = Field(pattern="^(drill|review|timed|cards)$")
    mode: str = Field(default="learning", pattern="^(learning|timed)$")
    minutes: int = 25


@router.post("/sessions")
def start_session(body: SessionIn, user=Depends(authenticate), db=Depends(get_db)):
    s = Session(user_id=user.id, purpose=body.purpose, mode=body.mode, minutes=body.minutes)
    db.add(s)
    db.commit()
    return {"id": s.id, "mode": s.mode, "purpose": s.purpose}


class EndIn(BaseModel):
    usefulness: int | None = Field(default=None, ge=1, le=5)


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, body: EndIn, user=Depends(authenticate), db=Depends(get_db)):
    s = db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Session not found")
    from .db import now
    s.ended, s.usefulness = s.ended or now(), body.usefulness
    db.commit()
    return {"ok": True}


class EventsIn(BaseModel):
    events: list[dict] = Field(max_length=500)


@router.post("/sessions/{session_id}/events")
def post_events(session_id: str, body: EventsIn, user=Depends(authenticate), db=Depends(get_db)):
    """Idempotent batch: (session, seq) is unique, so a retried flush never double-counts."""
    s = db.get(Session, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Session not found")
    have = set(db.scalars(select(Event.seq).where(Event.session_id == s.id)))
    stored = 0
    for e in body.events:
        seq = e.get("seq")
        if not isinstance(seq, int) or seq in have:
            continue
        db.add(Event(session_id=s.id, seq=seq, kind=str(e.get("kind", ""))[:40], data=json.dumps(e.get("data", {}))[:4000]))
        have.add(seq)
        stored += 1
    db.commit()
    return {"stored": stored, "duplicates": len(body.events) - stored}


def _skill_stats(db, user_id: str) -> tuple[list[priority.SkillStats], dict[str, float], dict[str, str]]:
    skills = db.scalars(select(Skill).where(Skill.parent_id.is_(None))).all()
    domain_section = {s.domain: s.section for s in skills}
    rows = db.execute(
        select(Item.skill_id, func.count(Attempt.id), func.sum(func.cast(Attempt.correct.is_(False), Integer)))
        .join(Item, Item.id == Attempt.item_id)
        .where(Attempt.user_id == user_id, Attempt.first_exposure.is_(True))
        .group_by(Item.skill_id)
    ).all()
    counts = {sid: (int(n or 0), int(m or 0)) for sid, n, m in rows}
    cutoff = (_today() - timedelta(days=30)).isoformat()
    open_by_skill = dict(
        db.execute(
            select(Ticket.skill_id, func.count()).where(Ticket.user_id == user_id, Ticket.created >= cutoff,
                                                         Ticket.state.in_(["OPEN", "REPAIRING", "RETRY_DUE", "TRANSFER_DUE", "REOPENED"]))
            .group_by(Ticket.skill_id)
        ).all()
    )
    stats = [priority.SkillStats(s.id, s.domain, *counts.get(s.id, (0, 0)), open_tickets_30d=open_by_skill.get(s.id, 0)) for s in skills]
    by_section: dict[str, list[int]] = {}
    for st in stats:
        sec = domain_section[st.domain]
        a, m = by_section.setdefault(sec, [0, 0])
        by_section[sec] = [a + st.attempts, m + st.misses]
    means = {sec: (m / a if a else 0.3) for sec, (a, m) in by_section.items()}
    return stats, means, domain_section


from datetime import timedelta  # noqa: E402

from sqlalchemy import Integer  # noqa: E402


@router.get("/today")
def today(minutes: int = 25, user=Depends(authenticate), db=Depends(get_db)):
    if minutes not in composer.SESSION_MINUTES:
        raise HTTPException(422, f"minutes must be one of {composer.SESSION_MINUTES}")
    d = _today()
    due_v = db.scalar(select(func.count()).select_from(Ticket).where(
        Ticket.user_id == user.id, Ticket.state.in_(["RETRY_DUE", "TRANSFER_DUE"]), Ticket.next_due <= d.isoformat())) or 0
    from .db import now as _now
    due_c = db.scalar(select(func.count()).select_from(Card).where(Card.user_id == user.id, Card.due <= _now())) or 0
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id))
    target = date.fromisoformat(plan.target_date) if plan else date(2027, 6, 5)
    days_left = (target - d).days
    tests = [date.fromisoformat(t.on_date) for t in db.scalars(select(SchoolTest).where(SchoolTest.user_id == user.id))]
    stats, means, dsec = _skill_stats(db, user.id)
    picks = priority.rank_skills(stats, means, days_left, slots=3, domain_section=dsec)
    focus = picks[0] if picks else None
    p = composer.compose(minutes, due_verifications=due_v, due_cards=due_c, focus_skill=focus[0] if focus else None,
                         focus_reason=f"Top priority ({focus[2]})" if focus else "", today=d, school_tests=tests)
    return {
        "minutes": p.minutes, "throttled": p.throttled, "days_to_target": days_left,
        "deferred_verifications": p.deferred_verifications,
        "blocks": [{"kind": b.kind, "minutes": b.minutes, "count": b.count, "reason": b.reason} for b in p.blocks],
        "focus_candidates": [{"skill_id": s, "priority": round(pr, 4), "reason": r} for s, pr, r in picks],
    }


@router.get("/cards/due")
def cards_due(user=Depends(authenticate), db=Depends(get_db), limit: int = 20):
    from .db import now as _now
    if not db.scalar(select(func.count()).select_from(Card).where(Card.user_id == user.id)):
        seed_cards(db, user.id)
    rows = db.scalars(select(Card).where(Card.user_id == user.id, Card.due <= _now()).order_by(Card.due).limit(min(limit, 50))).all()
    return [{"id": c.id, "kind": c.kind, "front": c.front, "back": c.back} for c in rows]


class CardReviewIn(BaseModel):
    correct: bool
    confidence: str | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    hinted: bool = False


@router.post("/cards/{card_id}/review")
def review_card(card_id: str, body: CardReviewIn, user=Depends(authenticate), db=Depends(get_db)):
    c = db.get(Card, card_id)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "Card not found")
    rating = srs.rating_from_behavior(correct=body.correct, confidence=body.confidence, elapsed_ms=body.elapsed_ms,
                                      p50_ms=8000, p90_ms=20000, hinted=body.hinted)
    c.state, due = srs.review(c.state, rating)
    c.due = due.isoformat()
    db.add(CardReview(card_id=c.id, rating=int(rating), elapsed_ms=body.elapsed_ms))
    db.commit()
    return {"rating": int(rating), "due": c.due}


class BenchmarkIn(BaseModel):
    source: str = Field(pattern="^(psat|bluebook|official_sat)$")
    taken_on: str
    rw_score: int | None = Field(default=None, ge=200, le=800)
    math_score: int | None = Field(default=None, ge=200, le=800)
    unseen: bool = False
    single_sitting: bool = False
    uninterrupted: bool = False
    unaided: bool = False


@router.post("/benchmarks")
def add_benchmark(body: BenchmarkIn, user=Depends(authenticate), db=Depends(get_db)):
    try:
        date.fromisoformat(body.taken_on)
    except ValueError:
        raise HTTPException(422, "taken_on must be YYYY-MM-DD") from None
    c = Conditions(body.unseen, body.single_sitting, body.uninterrupted, body.unaided)
    series = series_for(body.source, c)
    total = body.rw_score + body.math_score if body.rw_score and body.math_score else None
    b = Benchmark(user_id=user.id, series=series, taken_on=body.taken_on, rw_score=body.rw_score,
                  math_score=body.math_score, total_score=total, clean=series == "bluebook_clean",
                  conditions=json.dumps(c.__dict__))
    db.add(b)
    db.commit()
    return {"id": b.id, "series": series, "clean": b.clean, "total": total}


@router.get("/benchmarks")
def list_benchmarks(user=Depends(authenticate), db=Depends(get_db)):
    rows = db.scalars(select(Benchmark).where(Benchmark.user_id == user.id).order_by(Benchmark.taken_on)).all()
    out: dict[str, list] = {"psat": [], "bluebook_clean": [], "bluebook_exposed": [], "official_sat": []}
    for b in rows:
        out[b.series].append({"id": b.id, "taken_on": b.taken_on, "rw": b.rw_score, "math": b.math_score, "total": b.total_score})
    return out  # the clean series is the only one shown as truth


class SchoolTestIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    on_date: str


@router.post("/school-tests")
def add_school_test(body: SchoolTestIn, user=Depends(authenticate), db=Depends(get_db)):
    try:
        date.fromisoformat(body.on_date)
    except ValueError:
        raise HTTPException(422, "on_date must be YYYY-MM-DD") from None
    t = SchoolTest(user_id=user.id, title=body.title, on_date=body.on_date)
    db.add(t)
    db.commit()
    return {"id": t.id}


# ---- admin: corpus upload (parent only) -----------------------------------------------------
from fastapi import File, Form, UploadFile  # noqa: E402

from .auth import require_parent  # noqa: E402
from .corpus import ingest as ingest_mod  # noqa: E402
from .models import SourceDocument  # noqa: E402
from .upload_admission import serial_upload  # noqa: E402


@router.post("/admin/corpus/upload")
@serial_upload
def upload_source(kind: str = Form(...), file: UploadFile = File(...), user=Depends(require_parent), db=Depends(get_db)):
    from . import config
    data = file.file.read(config.MAX_UPLOAD + 1)
    if len(data) > config.MAX_UPLOAD:
        raise HTTPException(413, "File is too large")
    try:
        doc, created = ingest_mod.store_upload(db, data, kind)
    except ingest_mod.IngestError as error:
        raise HTTPException(422, str(error)) from None
    return {"id": doc.id, "created": created, "pages": doc.pages, "status": doc.status}


@router.get("/admin/corpus/documents")
def list_sources(user=Depends(require_parent), db=Depends(get_db)):
    rows = db.scalars(select(SourceDocument).order_by(SourceDocument.created.desc())).all()
    return [{"id": d.id, "kind": d.kind, "pages": d.pages, "status": d.status, "created": d.created} for d in rows]
