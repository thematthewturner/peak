"""Numeric-entry validator mirroring College Board's student-produced response rules.

Rules (PRD F3): up to 5 characters for positive answers, 6 for negative;
no mixed numbers, commas, $ or %. Fractions and decimals are allowed.
Returns a reason string when invalid so the UI can show the official-style message.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

_DECIMAL = re.compile(r"^-?(\d+\.?\d*|\.\d+)$")
_FRACTION = re.compile(r"^-?\d+/\d+$")


@dataclass(frozen=True)
class EntryResult:
    ok: bool
    reason: str | None = None
    value: Fraction | None = None


def _bad(reason: str) -> EntryResult:
    return EntryResult(False, reason)


def validate_entry(raw: str) -> EntryResult:
    s = raw.strip()
    if not s:
        return _bad("Enter an answer.")
    if " " in s:
        return _bad("Mixed numbers aren't accepted. Enter a fraction or decimal instead.")
    if any(c in s for c in ",$%"):
        return _bad("Commas, $ and % aren't accepted.")
    limit = 6 if s.startswith("-") else 5
    if len(s) > limit:
        return _bad(f"Too many characters: the limit is {limit}.")
    if _FRACTION.match(s):
        num, den = s.lstrip("-").split("/")
        if int(den) == 0:
            return _bad("The denominator can't be zero.")
        val = Fraction(int(num), int(den))
        return EntryResult(True, None, -val if s.startswith("-") else val)
    if _DECIMAL.match(s):
        return EntryResult(True, None, Fraction(s))
    return _bad("Use only digits, a decimal point, a slash, and a leading minus sign.")


def matches_key(raw: str, accepted: list[str]) -> bool:
    """True if the entry is valid and equals any accepted key by value."""
    res = validate_entry(raw)
    if not res.ok:
        return False
    return any((k := validate_entry(a)).ok and k.value == res.value for a in accepted)
