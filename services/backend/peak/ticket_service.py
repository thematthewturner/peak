"""Persistence glue between the pure verification ladder (tickets.py) and the database."""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select

from . import tickets as ladder
from .diagnose import AttemptFacts, Diagnosis, diagnose
from .exam import Section
from .models import Attempt, Item, Skill, Ticket, TicketEvidence
from .taxonomy import MICRO_SKILLS, Cause

OPEN_STATES = (ladder.State.RETRY_DUE, ladder.State.TRANSFER_DUE, ladder.State.CONFIRMED, ladder.State.MAINTAIN)


def _day(iso: str | None) -> date | None:
    return datetime.fromisoformat(iso).date() if iso else None


def family_of(item: Item) -> str:
    return item.family_id or f"item:{item.id}"


def to_pure(row: Ticket, evidence_rows: list[tuple[TicketEvidence, Attempt, Item]]) -> ladder.Ticket:
    counted = tuple(
        ladder.Counted(
            ladder.Evidence(
                attempt_id=a.id, correct=bool(a.correct), on=_day(a.created), family_id=family_of(i),
                first_exposure=a.first_exposure, aided=bool(json.loads(a.flags).get("aided")),
                mixed_unlabeled=bool(json.loads(a.flags).get("mixed_unlabeled")),
                under_pace=bool(json.loads(a.flags).get("under_pace")),
            ),
            e.reason,
        )
        for e, a, i in evidence_rows
        if e.counted
    )
    return ladder.Ticket(
        id=row.id, origin_family_id=None, state=ladder.State(row.state), repaired_on=_day(row.repaired_at),
        next_due=_day(row.next_due), timing_required=row.timing_required, counted=counted,
        seen_attempts=frozenset(e.attempt_id for e, _, _ in evidence_rows), reopen_reason=row.reopen_reason,
    )


def propose(db, attempt: Attempt, item: Item, *, cold_retry_correct: bool | None, p50=None, p90=None,
            requested_quantity_flag: bool = False) -> Diagnosis:
    skill = db.get(Skill, item.skill_id) if item.skill_id else None
    flags = json.loads(attempt.flags or "{}")
    facts = AttemptFacts(
        correct=bool(attempt.correct), confidence=attempt.confidence,
        section=Section(skill.section) if skill else Section.MATH, domain=skill.domain if skill else "algebra",
        elapsed_ms=attempt.elapsed_ms, p50_ms=p50, p90_ms=p90, cold_retry_correct=cold_retry_correct,
        desmos_used=bool(flags.get("desmos_used")), requested_quantity_flag=requested_quantity_flag,
    )
    attempt.cold_retry = cold_retry_correct
    return diagnose(facts)


def open_ticket(db, attempt: Attempt, item: Item, cause: Cause, micro_skill: str | None = None,
                rule: str | None = None) -> Ticket:
    """Idempotent per origin attempt. 'Careless' is never terminal: a micro-skill/cue is required."""
    existing = db.scalar(select(Ticket).where(Ticket.origin_attempt_id == attempt.id))
    if existing:
        return existing
    cue = next((m.cue for m in MICRO_SKILLS if m.key == micro_skill), None)
    if micro_skill and cue is None:
        raise ValueError("Unknown micro-skill")
    if cause in (Cause.EXECUTION, Cause.REQUESTED_QUANTITY, Cause.PACING) and not micro_skill:
        raise ValueError("Pick a named micro-skill: 'careless' is never a terminal label")
    if not item.skill_id:
        raise ValueError("Item has no skill to attach the ticket to")
    ticket = Ticket(
        user_id=attempt.user_id, skill_id=item.skill_id, origin_attempt_id=attempt.id, cause=cause.value,
        micro_skill=micro_skill, cue=cue, state=ladder.State.OPEN.value,
        timing_required=cause == Cause.PACING, rule=(rule or "").strip()[:200] or None,
    )
    db.add(ticket)
    if ticket.rule:
        # Her own rule becomes a spaced-retrieval card: she recalls it, then sees what she wrote.
        from . import srs
        from .models import Card, Skill
        skill = db.get(Skill, item.skill_id)
        label = next((m.label for m in MICRO_SKILLS if m.key == micro_skill), None) or (skill.skill if skill else "this skill")
        db.add(Card(user_id=attempt.user_id, kind="your rule", skill_id=item.skill_id,
                    front=f"Your rule for: {label}", back=ticket.rule, state=srs.new_state()))
    db.commit()
    return ticket


def _load(db, row: Ticket) -> ladder.Ticket:
    rows = db.execute(
        select(TicketEvidence, Attempt, Item)
        .join(Attempt, Attempt.id == TicketEvidence.attempt_id)
        .join(Item, Item.id == Attempt.item_id)
        .where(TicketEvidence.ticket_id == row.id)
        .order_by(TicketEvidence.created)
    ).all()
    origin = db.get(Attempt, row.origin_attempt_id)
    pure = to_pure(row, [(e, a, i) for e, a, i in rows])
    from dataclasses import replace
    return replace(pure, origin_family_id=family_of(db.get(Item, origin.item_id)))


def _save(row: Ticket, pure: ladder.Ticket):
    row.state = pure.state.value
    row.repaired_at = pure.repaired_on.isoformat() if pure.repaired_on else None
    row.next_due = pure.next_due.isoformat() if pure.next_due else None
    row.reopen_reason = pure.reopen_reason


def start_repair(db, row: Ticket, intervention: str) -> Ticket:
    pure = ladder.start_repair(_load(db, row))
    _save(row, pure)
    row.intervention = intervention
    db.commit()
    return row


def complete_repair(db, row: Ticket, on: date) -> Ticket:
    pure = ladder.complete_repair(_load(db, row), on)
    _save(row, pure)
    db.commit()
    return row


def apply_attempt(db, attempt: Attempt, item: Item) -> list[Ticket]:
    """Feed a new attempt into every awaiting ticket on the same skill. Idempotent per attempt."""
    if not item.skill_id:
        return []
    touched = []
    rows = db.scalars(
        select(Ticket).where(
            Ticket.user_id == attempt.user_id, Ticket.skill_id == item.skill_id,
            Ticket.state.in_([s.value for s in OPEN_STATES]),
        )
    ).all()
    flags = json.loads(attempt.flags or "{}")
    for row in rows:
        if db.scalar(select(TicketEvidence.id).where(TicketEvidence.ticket_id == row.id, TicketEvidence.attempt_id == attempt.id)):
            continue
        before = _load(db, row)
        ev = ladder.Evidence(
            attempt_id=attempt.id, correct=bool(attempt.correct), on=_day(attempt.created), family_id=family_of(item),
            first_exposure=attempt.first_exposure, aided=bool(flags.get("aided")),
            mixed_unlabeled=bool(flags.get("mixed_unlabeled")), under_pace=bool(flags.get("under_pace")),
        )
        counts, reason = ladder.classify(before, ev)
        after = ladder.apply_evidence(before, ev)
        db.add(TicketEvidence(ticket_id=row.id, attempt_id=attempt.id, counted=counts, reason=reason))
        _save(row, after)
        touched.append(row)
    db.commit()
    return touched
