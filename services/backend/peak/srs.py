"""FSRS for atomic rule cards only (PRD s5.4b). Ratings come from behavior, never self-report."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

DESIRED_RETENTION = 0.90
_scheduler = Scheduler(desired_retention=DESIRED_RETENTION)


def rating_from_behavior(
    *, correct: bool, confidence: str | None, elapsed_ms: int | None, p50_ms: int | None, p90_ms: int | None,
    hinted: bool = False,
) -> Rating:
    if not correct or hinted:
        return Rating.Again
    slow = bool(elapsed_ms and p90_ms and elapsed_ms > p90_ms)
    if confidence == "guess" or slow:
        return Rating.Hard
    fast = bool(elapsed_ms and p50_ms and elapsed_ms < p50_ms)
    if confidence == "sure" and fast:
        return Rating.Easy
    return Rating.Good


def new_state() -> str:
    return json.dumps(Card().to_dict())


def review(state_json: str, rating: Rating, now: datetime | None = None) -> tuple[str, datetime]:
    card = Card.from_dict(json.loads(state_json))
    card, _log = _scheduler.review_card(card, rating, review_datetime=now or datetime.now(timezone.utc))
    return json.dumps(card.to_dict()), card.due
