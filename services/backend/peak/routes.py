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
