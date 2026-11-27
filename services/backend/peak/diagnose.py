"""Deterministic cause proposal (PRD s5.2-5.3). Addison's confirmation always wins."""
from __future__ import annotations

from dataclasses import dataclass, field

from .exam import Section
from .taxonomy import Cause


@dataclass(frozen=True)
class AttemptFacts:
    correct: bool
    confidence: str | None  # sure|unsure|guess
    section: Section
    domain: str
    elapsed_ms: int | None = None
    p50_ms: int | None = None
    p90_ms: int | None = None
    cold_retry_correct: bool | None = None  # untimed retry before reveal
    entry_invalid: bool = False
    desmos_used: bool = False
    requested_quantity_flag: bool = False  # e.g. answer equals an intermediate value


@dataclass(frozen=True)
class Diagnosis:
    kind: str  # entrenched|lucky_guess|gap|fluent|slow_correct|miss|ok
    cause: Cause | None
    ticket_required: bool
    mastery_credit: bool
    reverify_days: tuple[int, ...] = ()
    reasons: tuple[str, ...] = field(default_factory=tuple)


RW_EVIDENCE_DOMAINS = {"craft_and_structure", "information_and_ideas", "expression_of_ideas"}


def _slow(f: AttemptFacts) -> bool:
    return bool(f.elapsed_ms and f.p90_ms and f.elapsed_ms > f.p90_ms)


def diagnose(f: AttemptFacts) -> Diagnosis:
    if f.correct:
        if f.confidence == "guess":
            return Diagnosis("lucky_guess", None, False, False, reasons=("right but guessed: no mastery credit",))
        if f.confidence == "sure" and _slow(f):
            return Diagnosis("slow_correct", Cause.PACING, True, True,
                             reasons=("right and sure but over p90 time for this skill",))
        if f.confidence == "sure":
            return Diagnosis("fluent", None, False, True, reasons=("right, sure, on pace",))
        return Diagnosis("ok", None, False, True, reasons=("right but unsure",))

    reasons = ["missed"]
    if f.entry_invalid:
        return Diagnosis("miss", Cause.ENTRY, True, False, reasons=("numeric entry was invalid",))
    entrenched = f.confidence == "sure"
    if entrenched:
        reasons.append("sure + wrong: entrenched misconception")
    if f.cold_retry_correct:
        # Knew it untimed: execution, pacing, requested quantity or tool misuse, never content.
        if f.requested_quantity_flag:
            cause = Cause.REQUESTED_QUANTITY
            reasons.append("cold retry right; answer matches an intermediate value")
        elif f.desmos_used and f.section == Section.MATH:
            cause = Cause.TOOL_MISUSE
            reasons.append("cold retry right; Desmos was used on the miss")
        elif _slow(f):
            cause = Cause.PACING
            reasons.append("cold retry right; time was over p90")
        else:
            cause = Cause.EXECUTION
            reasons.append("cold retry right untimed")
    elif f.cold_retry_correct is False:
        if f.section == Section.RW and f.domain in RW_EVIDENCE_DOMAINS:
            cause = Cause.EVIDENCE_DISTRACTOR
            reasons.append("cold retry wrong on a reading skill: distractor or evidence")
        else:
            cause = Cause.CONTENT_GAP
            reasons.append("cold retry wrong: content or setup gap")
    else:
        cause = Cause.CONTENT_GAP if f.confidence in ("unsure", "guess") else Cause.EXECUTION
        reasons.append("no cold retry yet; provisional")
    return Diagnosis(
        "entrenched" if entrenched else "miss",
        cause,
        True,
        False,
        reverify_days=(2, 7) if entrenched else (),
        reasons=tuple(reasons),
    )
