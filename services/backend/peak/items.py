"""Item store, student-safe projection and append-only attempts (PRD s9.2: items.py / attempts.py).

Invariants: no key or rationale leaves the server before an attempt exists; timed mode never
reveals; an attempt is never mutated; a repeated idempotency key returns the original attempt.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select

from .entry import matches_key, validate_entry
from .models import Attempt, Item


class AttemptError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def student_safe(item: Item) -> dict:
    """The only representation sent to a student before an attempt: never key, rationale or origin."""
    content = json.loads(item.content or "{}")
    return {
        "id": item.id,
        "format": item.format,
        "skill_id": item.skill_id,
        "difficulty": item.difficulty,
        "version": item.version,
        "passage": content.get("passage"),
        "stem": content.get("stem"),
        "choices": content.get("choices"),
        "figures": content.get("figures", []),
    }


def servable(item: Item, *, purpose: str) -> bool:
    if item.status != "verified":
        return False
    if item.benchmark_locked and purpose != "benchmark_review":
        return False  # benchmark forms stay clean: never served in drills
    return True


def has_attempt(db, user_id: str, item_id: str) -> bool:
    return bool(db.scalar(select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id, Attempt.item_id == item_id)))


def grade(item: Item, answer: str | None) -> tuple[bool | None, str | None]:
    """Return (correct, entry_error). Skips grade as wrong (correct=False) per the PRD metric."""
    if answer is None or answer == "":
        return False, None
    keys = json.loads(item.key or "[]")
    if item.format == "numeric":
        res = validate_entry(answer)
        if not res.ok:
            return None, res.reason
        return matches_key(answer, keys), None
    return answer.strip().upper() in {k.strip().upper() for k in keys}, None


def record_attempt(
    db,
    *,
    user_id: str,
    item: Item,
    idempotency_key: str,
    answer: str | None,
    session_id: str | None = None,
    confidence: str | None = None,
    elapsed_ms: int | None = None,
    flags: dict | None = None,
    purpose: str = "drill",
) -> tuple[Attempt, bool]:
    """Return (attempt, created). Idempotent on (user, key)."""
    existing = db.scalar(select(Attempt).where(Attempt.user_id == user_id, Attempt.idempotency_key == idempotency_key))
    if existing:
        if existing.item_id != item.id:
            raise AttemptError("Idempotency key already used for a different item", 409)
        return existing, False
    if not servable(item, purpose=purpose):
        raise AttemptError("Item is not available", 404)
    if confidence not in (None, "sure", "unsure", "guess"):
        raise AttemptError("confidence must be sure, unsure or guess")
    correct, entry_error = grade(item, answer)
    if entry_error:
        raise AttemptError(entry_error)
    first = not has_attempt(db, user_id, item.id)
    attempt = Attempt(
        user_id=user_id,
        session_id=session_id,
        item_id=item.id,
        item_version=item.version,
        first_exposure=first,
        answer=answer or None,
        correct=correct,
        confidence=confidence,
        elapsed_ms=elapsed_ms,
        flags=json.dumps(flags or {}),
        idempotency_key=idempotency_key,
    )
    db.add(attempt)
    db.commit()
    return attempt, True


def review(db, attempt: Attempt, item: Item, *, timed: bool) -> dict:
    """Reveal key and rationale only after an attempt exists, and never in timed mode."""
    if timed:
        return {"attempt_id": attempt.id, "correct": None, "revealed": False}
    return {
        "attempt_id": attempt.id,
        "correct": attempt.correct,
        "revealed": True,
        "key": json.loads(item.key or "[]"),
        "rationale": item.rationale,
    }
