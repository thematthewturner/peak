"""Seed rule cards (PRD s5.4b, s7): formulas missing from the reference sheet, grammar clusters,
transition families and Desmos syntax. Cue cards from confirmed tickets are added at runtime."""
from sqlalchemy import select

from . import srs
from .models import Card

# Math is written in TeX between $...$ (inline) or $$...$$ (display) and rendered with KaTeX in the app.
# `backticks` render monospace.
FORMULA = [
    ("Slope through $(x_1, y_1)$ and $(x_2, y_2)$", r"$$m = \dfrac{y_2 - y_1}{x_2 - x_1}$$"),
    ("Distance between two points", r"$$d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}$$"),
    ("Midpoint of two points", r"$$\left(\dfrac{x_1 + x_2}{2},\ \dfrac{y_1 + y_2}{2}\right)$$"),
    ("Discriminant of $ax^2 + bx + c$", r"$$b^2 - 4ac$$ Positive: two real roots. Zero: one root, so a line is tangent. Negative: no real roots."),
    ("Quadratic formula", r"$$x = \dfrac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$"),
    ("Vertex form of a parabola", r"$$y = a(x - h)^2 + k$$ The vertex is $(h, k)$. Watch the sign of $h$."),
    ("Sum and product of roots", r"For $ax^2 + bx + c = 0$: $$\text{sum} = -\dfrac{b}{a} \qquad \text{product} = \dfrac{c}{a}$$"),
    ("Circle, standard form", r"$$(x - h)^2 + (y - k)^2 = r^2$$ Center $(h, k)$, radius $r$, not $r^2$."),
    ("Exponential growth and decay", r"$$y = a \cdot b^{x}$$ $b > 1$ is growth, $0 < b < 1$ is decay. Read it from the base, not the coefficient."),
    ("SOHCAHTOA", r"$$\sin\theta = \dfrac{\text{opp}}{\text{hyp}} \qquad \cos\theta = \dfrac{\text{adj}}{\text{hyp}} \qquad \tan\theta = \dfrac{\text{opp}}{\text{adj}}$$"),
    ("Complementary angles", r"$$\sin\theta = \cos(90^\circ - \theta)$$"),
    ("Arc length", r"$$\text{arc} = \dfrac{\theta}{360^\circ} \cdot 2\pi r$$"),
    ("Sector area", r"$$\text{area} = \dfrac{\theta}{360^\circ} \cdot \pi r^2$$"),
    ("Hidden powers", r"$$1 = b^0 \qquad \sqrt{x} = x^{1/2} \qquad 9 = 3^2 \ (\text{not } 3^3) \qquad 8 = 2^3$$"),
]
# Earlier plain-text fronts, so existing cards are rewritten in place and keep their review schedule.
RENAMED = {
    "Slope through (x1,y1),(x2,y2)": "Slope through $(x_1, y_1)$ and $(x_2, y_2)$",
    "Discriminant of ax^2+bx+c": "Discriminant of $ax^2 + bx + c$",
    "Exponential growth/decay": "Exponential growth and decay",
}
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
    ("Regression in Desmos", "Use `~`, not `=`: `y1 ~ m x1 + b`. Check the table has columns `x1` and `y1`."),
    ("Use Desmos for", "Systems and intersections, radical equations (graph both sides), almost-factorable quadratics, equivalent-expression checks."),
    ("Use algebra for", "No-solution/infinite-solutions, tangency (b^2 - 4ac = 0), sum and product of roots, one-step linear items."),
]


def seed_cards(db, user_id: str) -> int:
    """Create missing cards and refresh the text of existing ones (FSRS state is kept). Returns cards created."""
    cards = {c.front: c for c in db.scalars(select(Card).where(Card.user_id == user_id))}
    n = 0
    for kind, rows in (("formula", FORMULA), ("grammar", GRAMMAR), ("transition", TRANSITIONS), ("desmos", DESMOS)):
        for front, back in rows:
            old = next((o for o, new in RENAMED.items() if new == front and o in cards), None)
            card = cards.get(front) or (cards.get(old) if old else None)
            if card is None:
                db.add(Card(user_id=user_id, kind=kind, front=front, back=back, state=srs.new_state()))
                n += 1
            elif (card.front, card.back) != (front, back):
                card.front, card.back = front, back
    db.commit()
    return n
