"""Form ledger rules (PRD principle 2): only unseen, single-sitting, unaided Bluebook forms are clean."""
from __future__ import annotations

from dataclasses import dataclass

REQUIRED = ("unseen", "single_sitting", "uninterrupted", "unaided")


@dataclass(frozen=True)
class Conditions:
    unseen: bool = False
    single_sitting: bool = False
    uninterrupted: bool = False
    unaided: bool = False


def is_clean(series: str, c: Conditions) -> bool:
    return series in ("bluebook_clean", "bluebook") and all(getattr(c, k) for k in REQUIRED)


def series_for(source: str, c: Conditions) -> str:
    if source == "psat":
        return "psat"
    if source == "official_sat":
        return "official_sat"
    return "bluebook_clean" if is_clean("bluebook_clean", c) else "bluebook_exposed"


def stall(prev_total: int, last_total: int, weeks_apart: float, threshold: int = 40) -> bool:
    """Stall rule: two clean benchmarks 6+ weeks apart that moved less than ~40 points."""
    return weeks_apart >= 6 and (last_total - prev_total) < threshold
