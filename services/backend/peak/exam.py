"""Digital SAT structure, held as data (PRD s7, s9.2).

This module never computes scaled scores; that stays in Bluebook.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Section(StrEnum):
    RW = "rw"
    MATH = "math"


class ItemFormat(StrEnum):
    MULTIPLE_CHOICE = "mc"
    NUMERIC_ENTRY = "numeric"


@dataclass(frozen=True)
class ModuleSpec:
    section: Section
    items: int
    minutes: int

    @property
    def seconds_per_item(self) -> float:
        return self.minutes * 60 / self.items


# Two modules per section; Module 1 routes Module 2.
MODULES: dict[Section, ModuleSpec] = {
    Section.RW: ModuleSpec(Section.RW, items=27, minutes=32),
    Section.MATH: ModuleSpec(Section.MATH, items=22, minutes=35),
}
MODULES_PER_SECTION = 2

# Per-item caps used by the stamina ladder (PRD s5.7), in seconds.
ITEM_CAP_SECONDS = {"rw_conventions": 45, "math_standard": 60, "dense_reading": 90, "math_hard": 90}

# Two-pass rule nudges (PRD s7), in seconds.
NUDGE_RW_SECONDS = 90
NUDGE_MATH_SETUP_SECONDS = 45

# Official domain shares of scored items.
DOMAIN_SHARES: dict[str, float] = {
    "craft_and_structure": 0.28,
    "information_and_ideas": 0.26,
    "standard_english_conventions": 0.26,
    "expression_of_ideas": 0.20,
    "algebra": 0.35,
    "advanced_math": 0.35,
    "problem_solving_data_analysis": 0.15,
    "geometry_trigonometry": 0.15,
}
