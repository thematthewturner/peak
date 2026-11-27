"""Session composer for Today (PRD s5.6). Every block carries a reason; backlog never stacks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SESSION_MINUTES = (5, 15, 25, 40)
SCHOOL_TEST_THROTTLE_DAYS = 3
MIN_PER_ITEM = 1.5  # planning average


@dataclass(frozen=True)
class Block:
    kind: str  # verification|cards|focus|mixed
    minutes: float
    reason: str
    count: int = 0


@dataclass(frozen=True)
class SessionPlan:
    minutes: int
    blocks: tuple[Block, ...]
    deferred_verifications: int = 0  # re-ranked, not deleted
    throttled: bool = False


def school_test_within(today: date, tests: list[date], days: int = SCHOOL_TEST_THROTTLE_DAYS) -> bool:
    return any(0 <= (t - today).days <= days for t in tests)


def compose(
    minutes: int,
    *,
    due_verifications: int,
    due_cards: int,
    focus_skill: str | None,
    focus_reason: str = "",
    today: date | None = None,
    school_tests: list[date] | None = None,
) -> SessionPlan:
    if minutes not in SESSION_MINUTES:
        raise ValueError(f"minutes must be one of {SESSION_MINUTES}")
    throttled = bool(today and school_tests and school_test_within(today, school_tests))
    if throttled:
        minutes = 5
    if minutes == 5:
        cards = min(due_cards, 8)
        why = "School test coming up: 5-minute maintenance" if throttled else "5-minute session: rule cards only"
        blocks = (Block("cards", 5, f"{why} ({due_cards} due)", cards),) if cards else ()
        return SessionPlan(5, blocks, deferred_verifications=due_verifications, throttled=throttled)

    budget_v = minutes * 0.30
    max_v_items = int(budget_v / MIN_PER_ITEM)
    take_v = min(due_verifications, max_v_items)
    blocks: list[Block] = []
    used = 0.0
    if take_v:
        m = take_v * MIN_PER_ITEM
        blocks.append(Block("verification", m, f"Due: {due_verifications} repair check(s)", take_v))
        used += m
    if due_cards:
        m = min(5.0, due_cards * 0.5)
        blocks.append(Block("cards", m, f"{due_cards} rule card(s) due", int(m / 0.5)))
        used += m
    mixed_m = round(minutes * 0.20, 1)
    focus_m = max(0.0, round(minutes - used - mixed_m, 1))
    if focus_skill and focus_m > 0:
        blocks.append(Block("focus", focus_m, focus_reason or f"Top priority: {focus_skill}", int(focus_m / MIN_PER_ITEM)))
    else:
        mixed_m += focus_m
    blocks.append(Block("mixed", mixed_m, "Unlabeled mixed finish, one from the weaker section", max(1, int(mixed_m / MIN_PER_ITEM))))
    return SessionPlan(minutes, tuple(blocks), deferred_verifications=due_verifications - take_v)
