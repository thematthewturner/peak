"""Official SAT domains plus Addison's seeded micro-skills and cues (PRD s5.2).

Causes are fixed and small. Micro-skills are open-ended and carry a one-line
cue shown in the runner when the pattern is likely.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .exam import DOMAIN_SHARES, Section


class Cause(StrEnum):
    CONTENT_GAP = "content_gap"
    SETUP_METHOD = "setup_method"
    REQUESTED_QUANTITY = "requested_quantity"
    EXECUTION = "execution"
    ENTRY = "entry"
    EVIDENCE_DISTRACTOR = "evidence_distractor"
    PACING = "pacing"
    TOOL_MISUSE = "tool_misuse"


@dataclass(frozen=True)
class Domain:
    key: str
    section: Section
    name: str

    @property
    def share(self) -> float:
        return DOMAIN_SHARES[self.key]


DOMAINS: tuple[Domain, ...] = (
    Domain("craft_and_structure", Section.RW, "Craft & Structure"),
    Domain("information_and_ideas", Section.RW, "Information & Ideas"),
    Domain("standard_english_conventions", Section.RW, "Standard English Conventions"),
    Domain("expression_of_ideas", Section.RW, "Expression of Ideas"),
    Domain("algebra", Section.MATH, "Algebra"),
    Domain("advanced_math", Section.MATH, "Advanced Math"),
    Domain("problem_solving_data_analysis", Section.MATH, "Problem-Solving & Data Analysis"),
    Domain("geometry_trigonometry", Section.MATH, "Geometry & Trigonometry"),
)


@dataclass(frozen=True)
class MicroSkill:
    key: str
    cause: Cause
    domain: str | None  # None = cross-domain
    label: str
    cue: str


# Seeded from her Honors Algebra 2 error log (Oct 2026).
MICRO_SKILLS: tuple[MicroSkill, ...] = (
    MicroSkill("hidden_powers", Cause.CONTENT_GAP, "advanced_math",
               "Hidden powers (1 = b^0, sqrt = 1/2)", "Rule card plus a worked example"),
    MicroSkill("growth_vs_decay", Cause.CONTENT_GAP, "advanced_math",
               "Growth vs decay: read it from the base, not the coefficient", "Rule card plus a worked example"),
    MicroSkill("format_shift_abandonment", Cause.SETUP_METHOD, None,
               "Drops a known routine when the layout changes", "Same math, new costume. What's the routine?"),
    MicroSkill("desmos_vs_algebra", Cause.SETUP_METHOD, "algebra",
               "Picks Desmos when algebra is faster", "Decision card: algebra or Desmos?"),
    MicroSkill("requested_quantity", Cause.REQUESTED_QUANTITY, None,
               "Answers x when asked for 6x; radius vs diameter; one root vs sum", "Re-read the last line before you enter."),
    MicroSkill("skips_plug_back", Cause.EXECUTION, "algebra",
               "Skips the plug-back check", "Plug it back in"),
    MicroSkill("sign_slips", Cause.EXECUTION, "advanced_math",
               "Sign slips when factoring", "Plug it back in"),
    MicroSkill("wrong_powers", Cause.EXECUTION, "advanced_math",
               "Wrong powers (9 = 3^3 recurring)", "Write the power out before you simplify"),
    MicroSkill("numeric_entry_format", Cause.ENTRY, None,
               "Mixed numbers, too many characters, dropped negative", "Strict-entry validation with a reason"),
    MicroSkill("distractor_traps", Cause.EVIDENCE_DISTRACTOR, "craft_and_structure",
               "Recycled language, absolutes, scope shift, true but off-goal", "Point to the line that proves it."),
    MicroSkill("one_problem_time_sink", Cause.PACING, None,
               "Spends 3+ minutes on one item", "90-second nudge: flag and move"),
    MicroSkill("desmos_syntax", Cause.TOOL_MISUSE, None,
               "Typed = instead of ~ in a regression; misread a zoomed graph", "Desmos syntax card"),
)

_DOMAIN_KEYS = {d.key for d in DOMAINS}
for _m in MICRO_SKILLS:
    assert _m.domain is None or _m.domain in _DOMAIN_KEYS, _m.key


# Official Digital SAT skill names per domain (College Board specifications).
OFFICIAL_SKILLS: dict[str, tuple[str, ...]] = {
    "craft_and_structure": ("Words in Context", "Text Structure and Purpose", "Cross-Text Connections"),
    "information_and_ideas": (
        "Central Ideas and Details", "Command of Evidence", "Inferences",
    ),
    "standard_english_conventions": ("Boundaries", "Form, Structure, and Sense"),
    "expression_of_ideas": ("Rhetorical Synthesis", "Transitions"),
    "algebra": (
        "Linear equations in one variable", "Linear functions", "Linear equations in two variables",
        "Systems of two linear equations in two variables", "Linear inequalities in one or two variables",
    ),
    "advanced_math": (
        "Equivalent expressions", "Nonlinear equations in one variable and systems of equations in two variables",
        "Nonlinear functions",
    ),
    "problem_solving_data_analysis": (
        "Ratios, rates, proportional relationships, and units", "Percentages",
        "One-variable data: distributions and measures of center and spread",
        "Two-variable data: models and scatterplots", "Probability and conditional probability",
        "Inference from sample statistics and margin of error", "Evaluating statistical claims",
    ),
    "geometry_trigonometry": ("Area and volume", "Lines, angles, and triangles", "Right triangles and trigonometry", "Circles"),
}


def skill_id(domain: str, name: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{domain}.{slug[:48]}"
