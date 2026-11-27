"""The verification ladder (PRD s5.4a): a pure, transparent state machine.

OPEN -> REPAIRING -> RETRY_DUE (next day) -> TRANSFER_DUE (7+ days, unlabeled mixed set)
-> CONFIRMED -> MAINTAIN; a relapse moves to REOPENED.

Only fresh, unaided, first-exposure evidence counts. A same-family item or a repeat cannot
close a ticket. No I/O here: callers persist the returned state and evidence rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import StrEnum

TRANSFER_MIN_DAYS = 7
RETRY_DAYS = 1
ENTRENCHED_RECHECK_DAYS = (2, 7)  # sure+wrong: re-verify at 2-3 days and again at about 7


class State(StrEnum):
    OPEN = "OPEN"
    REPAIRING = "REPAIRING"
    RETRY_DUE = "RETRY_DUE"
    TRANSFER_DUE = "TRANSFER_DUE"
    CONFIRMED = "CONFIRMED"
    MAINTAIN = "MAINTAIN"
    REOPENED = "REOPENED"


@dataclass(frozen=True)
class Evidence:
    attempt_id: str
    correct: bool
    on: date
    family_id: str | None
    first_exposure: bool = True
    aided: bool = False
    mixed_unlabeled: bool = False
    under_pace: bool = False


@dataclass(frozen=True)
class Counted:
    evidence: Evidence
    reason: str


@dataclass(frozen=True)
class Ticket:
    id: str
    origin_family_id: str | None
    state: State = State.OPEN
    repaired_on: date | None = None
    next_due: date | None = None
    timing_required: bool = False
    counted: tuple[Counted, ...] = field(default_factory=tuple)
    seen_attempts: frozenset[str] = frozenset()
    reopen_reason: str | None = None


def start_repair(t: Ticket) -> Ticket:
    if t.state not in (State.OPEN, State.REOPENED):
        raise ValueError(f"cannot start repair from {t.state}")
    return replace(t, state=State.REPAIRING)


def complete_repair(t: Ticket, on: date, *, entrenched: bool = False) -> Ticket:
    """Repair done: the next-day retry is due. Entrenched (sure+wrong) errors recheck later too."""
    if t.state != State.REPAIRING:
        raise ValueError(f"cannot complete repair from {t.state}")
    return replace(
        t, state=State.RETRY_DUE, repaired_on=on, next_due=on + timedelta(days=RETRY_DAYS), counted=(),
        reopen_reason=None,
    )


def classify(t: Ticket, ev: Evidence) -> tuple[bool, str]:
    """Return (counts, reason). Transparent so the UI can explain why evidence was ignored."""
    if ev.attempt_id in t.seen_attempts:
        return False, "duplicate attempt"
    if t.state not in (State.RETRY_DUE, State.TRANSFER_DUE, State.CONFIRMED, State.MAINTAIN):
        return False, "ticket is not awaiting evidence"
    if t.repaired_on is not None and ev.on <= t.repaired_on:
        return False, "same day as the repair"
    if ev.aided:
        return False, "aided attempt"
    if not ev.first_exposure:
        return False, "not a first exposure"
    if ev.family_id is not None and ev.family_id == t.origin_family_id:
        return False, "same item family as the original miss"
    if any(c.evidence.family_id == ev.family_id and ev.family_id is not None for c in t.counted if c.evidence.correct):
        return False, "item family already used as evidence"
    return True, "fresh, unaided, first exposure from a new family"


def is_confirmed(t: Ticket) -> bool:
    good = [c.evidence for c in t.counted if c.evidence.correct]
    if len(good) < 2:
        return False
    if len({e.on for e in good}) < 2:
        return False
    if len({e.family_id for e in good}) < 2:
        return False
    if t.repaired_on is None:
        return False
    delayed = any(
        e.mixed_unlabeled and (e.on - t.repaired_on).days >= TRANSFER_MIN_DAYS for e in good
    )
    if not delayed:
        return False
    if t.timing_required and not any(e.under_pace for e in good):
        return False
    return True


def apply_evidence(t: Ticket, ev: Evidence) -> Ticket:
    """Idempotent: re-applying the same attempt never advances a ticket twice."""
    counts, reason = classify(t, ev)
    seen = t.seen_attempts | {ev.attempt_id}
    if not counts:
        return replace(t, seen_attempts=seen)
    if not ev.correct:
        # A fresh, unaided miss is a relapse: reopen with the reason attached.
        return replace(
            t,
            state=State.REOPENED,
            reopen_reason=f"missed fresh item on {ev.on.isoformat()}",
            counted=(),
            next_due=None,
            seen_attempts=seen,
        )
    counted = t.counted + (Counted(ev, reason),)
    nxt = replace(t, counted=counted, seen_attempts=seen)
    if is_confirmed(nxt):
        return replace(nxt, state=State.CONFIRMED, next_due=None)
    if t.state == State.RETRY_DUE:
        due = (t.repaired_on or ev.on) + timedelta(days=TRANSFER_MIN_DAYS)
        return replace(nxt, state=State.TRANSFER_DUE, next_due=due)
    return nxt


def maintain(t: Ticket) -> Ticket:
    if t.state != State.CONFIRMED:
        raise ValueError("only confirmed tickets move to maintenance")
    return replace(t, state=State.MAINTAIN)


def needs_new_item(t: Ticket, available_families: set[str]) -> bool:
    """True when no unused family exists: show 'needs a new item' rather than counting a repeat."""
    used = {c.evidence.family_id for c in t.counted} | {t.origin_family_id}
    return not (available_families - used)


def recheck_days(entrenched: bool) -> tuple[int, ...]:
    return ENTRENCHED_RECHECK_DAYS if entrenched else ()
