"""Seed rule cards (PRD s5.4b, s7): formulas missing from the reference sheet, grammar clusters,
transition families and Desmos syntax. Cue cards from confirmed tickets are added at runtime."""
from sqlalchemy import select

from . import srs
from .models import Card

FORMULA = [
    ("Slope through (x1,y1),(x2,y2)", "m = (y2 - y1)/(x2 - x1)"),
    ("Distance between two points", "d = sqrt((x2-x1)^2 + (y2-y1)^2)"),
    ("Midpoint of two points", "((x1+x2)/2, (y1+y2)/2)"),
    ("Discriminant of ax^2+bx+c", "b^2 - 4ac. Positive: 2 real roots; 0: one (tangent); negative: none"),
    ("Quadratic formula", "x = (-b ± sqrt(b^2 - 4ac)) / 2a"),
    ("Vertex form of a parabola", "y = a(x - h)^2 + k, vertex (h, k)"),
    ("Sum and product of roots", "Sum = -b/a, product = c/a"),
    ("Circle, standard form", "(x - h)^2 + (y - k)^2 = r^2, center (h, k)"),
    ("Exponential growth/decay", "y = a(b)^x: b > 1 growth, 0 < b < 1 decay. Read it from the base, not the coefficient"),
    ("SOHCAHTOA", "sin = opp/hyp, cos = adj/hyp, tan = opp/adj"),
    ("Complementary angles", "sin(θ) = cos(90° - θ)"),
    ("Arc length", "(central angle / 360°) × 2πr"),
    ("Sector area", "(central angle / 360°) × πr^2"),
    ("Hidden powers", "1 = b^0, sqrt(x) = x^(1/2), 9 = 3^2 (not 3^3), 8 = 2^3"),
]
GRAMMAR = [
    ("Clause boundaries", "Period = semicolon = comma + FANBOYS. A colon only after an independent clause."),
    ("Nonessential elements", "Punctuation before and after must match: two commas, two dashes or two parentheses."),
    ("Subject-verb agreement", "Find the true subject; ignore intervening phrases."),
    ("Apostrophes", "its/it's, their/they're, whose/who's: possessive pronouns never take an apostrophe."),
    ("Tense and modifiers", "Keep tense consistent; the noun right after a modifying phrase must be the thing it modifies."),
]
TRANSITIONS = [
    ("Contrast transitions", "however, nevertheless, in contrast, yet, still"),
    ("Cause and effect transitions", "therefore, thus, consequently, as a result"),
    ("Continuation transitions", "moreover, furthermore, also, in addition, similarly"),
    ("Sequence transitions", "first, next, then, finally, subsequently"),
    ("Emphasis and example transitions", "in fact, indeed, for example, for instance, specifically"),
]
DESMOS = [
    ("Regression in Desmos", "Use ~ not =. y1 ~ mx1 + b. Check the table has x1 and y1 columns."),
    ("Use Desmos for", "Systems and intersections, radical equations (graph both sides), almost-factorable quadratics, equivalent-expression checks."),
    ("Use algebra for", "No-solution/infinite-solutions, tangency (b^2 - 4ac = 0), sum and product of roots, one-step linear items."),
]


def seed_cards(db, user_id: str) -> int:
    existing = {c.front for c in db.scalars(select(Card).where(Card.user_id == user_id))}
    n = 0
    for kind, rows in (("formula", FORMULA), ("grammar", GRAMMAR), ("transition", TRANSITIONS), ("desmos", DESMOS)):
        for front, back in rows:
            if front not in existing:
                db.add(Card(user_id=user_id, kind=kind, front=front, back=back, state=srs.new_state()))
                n += 1
    db.commit()
    return n
