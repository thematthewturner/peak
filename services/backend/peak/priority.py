"""Drill priority (PRD s5.4c): orders work, it is not a score conversion."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .exam import DOMAIN_SHARES

K_SMOOTH = 8
EXPLORE_SHARE = 0.15
COURSEWORK_BOOST = 1.25
HARD_UNLOCK_ACCURACY = 0.75
HARD_UNLOCK_WINDOW = 12


@dataclass(frozen=True)
class SkillStats:
    skill_id: str
    domain: str
    attempts: int
    misses: int
    open_tickets_30d: int = 0
    coursework_aligned: bool = False
    recent_medium: tuple[bool, ...] = ()  # last fresh Medium results, newest last


def smoothed_miss_rate(misses: int, attempts: int, section_mean: float, k: int = K_SMOOTH) -> float:
    return (misses + k * section_mean) / (attempts + k)


def test_proximity(days_to_test: int | None) -> float:
    """Shift weight toward timed and robustness work inside 6 weeks of a test."""
    if days_to_test is None or days_to_test >= 42:
        return 1.0
    return 1.0 + 0.5 * (42 - max(days_to_test, 0)) / 42


def skill_priority(s: SkillStats, section_mean: float, days_to_test: int | None) -> float:
    w = DOMAIN_SHARES[s.domain]
    m = smoothed_miss_rate(s.misses, s.attempts, section_mean)
    boost = COURSEWORK_BOOST if s.coursework_aligned else 1.0
    return w * m * (1 + 0.5 * s.open_tickets_30d) * test_proximity(days_to_test) * boost


def hard_unlocked(s: SkillStats) -> bool:
    window = s.recent_medium[-HARD_UNLOCK_WINDOW:]
    return len(window) >= HARD_UNLOCK_WINDOW and sum(window) / len(window) >= HARD_UNLOCK_ACCURACY


def rank_skills(
    stats: list[SkillStats],
    section_means: dict[str, float],
    days_to_test: int | None = None,
    slots: int = 5,
    seed: int | None = None,
    domain_section: dict[str, str] | None = None,
) -> list[tuple[str, float, str]]:
    """Return (skill_id, priority, reason) for `slots` picks; ~15% go to under-measured skills."""
    domain_section = domain_section or {}
    scored = []
    for s in stats:
        mean = section_means.get(domain_section.get(s.domain, ""), 0.3)
        scored.append((skill_priority(s, mean, days_to_test), s))
    scored.sort(key=lambda p: (-p[0], p[1].skill_id))
    n_explore = round(slots * EXPLORE_SHARE) if slots >= 4 else 0
    picks = [(s.skill_id, p, "highest priority") for p, s in scored[: slots - n_explore]]
    chosen = {pid for pid, _, _ in picks}
    rng = random.Random(seed)
    thin = [(p, s) for p, s in scored if s.skill_id not in chosen and s.attempts < K_SMOOTH]
    rng.shuffle(thin)
    for p, s in thin[:n_explore]:
        picks.append((s.skill_id, p, "under-measured: exploration slot"))
    for p, s in scored:  # backfill if exploration pool was short
        if len(picks) >= slots:
            break
        if s.skill_id not in {x[0] for x in picks}:
            picks.append((s.skill_id, p, "highest priority"))
    return picks
