"""Build one study session as an ordered queue of steps, following the score guide (docs: SAT_SCORE_GUIDE s5).

  1. Re-attempts from her log (spaced retrieval, s4.3/s4.6): the original missed question at its 2-day mark,
     plus a fresh question of the same skill as proof. Later checks hide inside the mixed set, unlabeled.
  2. Rule cards due (FSRS), inline.
  3. New math skill only: worked examples first, then a couple of first tries (s4.4, expertise reversal).
  4. A mixed set within one section (interleaving, s4.2): ~60% her priority skills, ~40% the rest,
     ordered so the same domain rarely appears twice in a row. Difficulty is her comfort band, one up when earned.

Every step carries the reason it is there, so the UI can coach instead of just serving questions.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from . import composer, priority
from .models import Attempt, Benchmark, Card, Item, Plan, SchoolTest, Session, Skill, Ticket

PER_QUESTION_MIN = 2.0  # answer plus check: the guide's 15-20 questions in 30-40 minutes
PRIORITY_SHARE = 0.6
DUE_STATES = ("RETRY_DUE", "TRANSFER_DUE", "CONFIRMED")


# ---- her numbers ---------------------------------------------------------------------------
def skill_stats(db, user_id: str) -> dict[str, dict]:
    """First-exposure answers per skill (worked examples excluded), newest last."""
    rows = db.execute(
        select(Item.skill_id, Item.difficulty, Attempt.correct, Attempt.confidence, Attempt.created)
        .join(Item, Item.id == Attempt.item_id)
        .where(Attempt.user_id == user_id, Attempt.first_exposure.is_(True), Attempt.correct.is_not(None))
        .order_by(Attempt.created)
    ).all()
    out: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "correct": 0, "recent": [], "medium_recent": [],
                                                "sure": 0, "sure_wrong": 0, "last": None})
    for sid, diff, correct, conf, created in rows:
        s = out[sid]
        s["last"] = created
        s["attempts"] += 1
        s["correct"] += bool(correct)
        s["recent"] = (s["recent"] + [bool(correct)])[-10:]
        if diff == "medium":
            s["medium_recent"] = (s["medium_recent"] + [bool(correct)])[-12:]
        if conf == "sure":
            s["sure"] += 1
            s["sure_wrong"] += not correct
    return dict(out)


def latest_total(db, user_id: str) -> int | None:
    b = db.scalar(select(Benchmark).where(Benchmark.user_id == user_id, Benchmark.total_score.is_not(None))
                  .order_by(Benchmark.taken_on.desc()).limit(1))
    return b.total_score if b else None


def target_difficulty(stats: dict | None) -> str:
    """Her comfort band, one up when earned (s5 'difficulty one band above her comfort level')."""
    if not stats or stats["attempts"] < 4:
        return "medium"
    if priority.hard_unlocked(priority.SkillStats("", "algebra", stats["attempts"], 0,
                                                  recent_medium=tuple(stats["medium_recent"]))):
        return "hard"
    recent = stats["recent"]
    return "medium" if sum(recent) / len(recent) >= 0.6 else "easy"


def choose_section(db, user_id: str, today: date) -> str:
    """Math gets ~60% of sessions (her weaker section, PRD s1); the week's mix decides the next one."""
    plan = db.scalar(select(Plan).where(Plan.user_id == user_id))
    share = plan.math_share if plan else PRIORITY_SHARE
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    sections = [json.loads(s.plan or "{}").get("section") for s in
                db.scalars(select(Session).where(Session.user_id == user_id, Session.started >= week_start))]
    sections = [s for s in sections if s in ("math", "rw")]
    if not sections:
        return "math"
    return "math" if sections.count("math") / len(sections) < share else "rw"


# ---- picking questions -----------------------------------------------------------------------
def pick(db, user_id, *, section=None, skill_id=None, difficulty=None, exclude=(), avoid_families=()) -> Item | None:
    seen = select(Attempt.item_id).where(Attempt.user_id == user_id)
    q = (select(Item).join(Skill, Skill.id == Item.skill_id)
         .where(Item.status == "verified", Item.benchmark_locked.is_(False), Item.id.not_in(seen)))
    if section:
        q = q.where(Skill.section == section)
    if skill_id:
        q = q.where(Item.skill_id == skill_id)
    if exclude:
        q = q.where(Item.id.not_in(list(exclude)))
    order = [difficulty] + [d for d in ("medium", "easy", "hard") if d != difficulty] if difficulty else [None]
    for d in order:
        qq = q.where(Item.difficulty == d) if d else q
        for item in db.scalars(qq.order_by(func.random()).limit(25)):
            if item.family_id and item.family_id in avoid_families:
                continue
            return item
    return None


def interleave(steps: list[dict], rng: random.Random) -> list[dict]:
    """Order so the same domain doesn't appear twice in a row (s4.2: the hard part is recognizing the type).
    Always draw from the domain with the most left that differs from the last one; this separates them
    whenever it's possible (no domain holds more than half the set)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in steps:
        groups[s["domain"]].append(s)
    for g in groups.values():
        rng.shuffle(g)
    out: list[dict] = []
    while any(groups.values()):
        last = out[-1]["domain"] if out else None
        ranked = sorted((d for d in groups if groups[d]), key=lambda d: (-len(groups[d]), rng.random()))
        pick_d = next((d for d in ranked if d != last), ranked[0])
        out.append(groups[pick_d].pop())
    return out


# ---- the queue -------------------------------------------------------------------------------
def build(db, user_id: str, minutes: int, today: date, seed: int | None = None, *,
          section: str | None = None, only_skill: str | None = None) -> dict:
    """only_skill: 'Just this skill' from Change session. Everything stays spaced and fresh, but unmixed."""
    rng = random.Random(seed)
    skills = {s.id: s for s in db.scalars(select(Skill).where(Skill.parent_id.is_(None)))}
    stats = skill_stats(db, user_id)
    due = db.scalars(select(Ticket).where(Ticket.user_id == user_id, Ticket.state.in_(DUE_STATES),
                                          Ticket.next_due <= today.isoformat()).order_by(Ticket.next_due)).all()
    due_cards = db.scalar(select(func.count()).select_from(Card).where(
        Card.user_id == user_id, Card.due <= datetime.now(timezone.utc).isoformat())) or 0
    if only_skill and only_skill in skills:
        section = skills[only_skill].section
    section = section if section in ("math", "rw") else choose_section(db, user_id, today)
    tests = [date.fromisoformat(t.on_date) for t in db.scalars(select(SchoolTest).where(SchoolTest.user_id == user_id))]

    # Priority within the chosen section: domain weight x her smoothed miss rate (guide s3 priority rule).
    in_section = [s for s in skills.values() if s.section == section]
    sstats = [priority.SkillStats(s.id, s.domain, stats.get(s.id, {}).get("attempts", 0),
                                  stats.get(s.id, {}).get("attempts", 0) - stats.get(s.id, {}).get("correct", 0))
              for s in in_section]
    tot_a = sum(x.attempts for x in sstats)
    mean = (sum(x.misses for x in sstats) / tot_a) if tot_a else 0.35
    ranked = sorted(sstats, key=lambda x: -priority.skill_priority(x, mean, (date(2027, 6, 5) - today).days))
    # Top priorities come from different domains, so the mixed set can actually interleave.
    top: list[str] = []
    for x in ranked:
        if len(top) < 3 and all(skills[t].domain != skills[x.skill_id].domain for t in top):
            top.append(x.skill_id)
    top += [x.skill_id for x in ranked if x.skill_id not in top][: 3 - len(top)]
    if only_skill and only_skill in skills:
        top = [only_skill]
    focus = top[0] if top else None

    plan = composer.compose(minutes, due_verifications=len(due), due_cards=due_cards, focus_skill=focus,
                            today=today, school_tests=tests)
    block_min = {b.kind: b.minutes for b in plan.blocks}
    used: set[str] = set()
    steps: list[dict] = []
    hidden_proofs: list[dict] = []

    def step(kind, item, block, reason, flags=None, **extra):
        used.add(item.id)
        sk = skills.get(item.skill_id)
        return {"kind": kind, "item_id": item.id, "skill_id": item.skill_id, "domain": sk.domain if sk else "",
                "block": block, "reason": reason, "flags": flags or {}, **extra}

    # 1. Re-attempts from her log.
    for t in due[: max(0, len(due) - plan.deferred_verifications)]:
        origin = db.get(Attempt, t.origin_attempt_id)
        origin_item = db.get(Item, origin.item_id) if origin else None
        avoid = {origin_item.family_id} if origin_item and origin_item.family_id else set()
        label = t.rule or t.cue or "your fix"
        if t.state == "RETRY_DUE":
            if origin_item:
                steps.append(step("reattempt", origin_item, "warmup", "From your log: the question you missed, two days later",
                                  ticket_id=t.id, rule=t.rule))
            proof = pick(db, user_id, skill_id=t.skill_id, difficulty=target_difficulty(stats.get(t.skill_id)),
                         exclude=used, avoid_families=avoid)
            if proof:
                steps.append(step("question", proof, "warmup", f"A fresh one of the same kind. Use your rule: {label}",
                                  ticket_id=t.id))
        else:
            proof = pick(db, user_id, skill_id=t.skill_id, exclude=used, avoid_families=avoid)
            if proof:
                why = "3-week check" if t.state == "CONFIRMED" else "1-week proof"
                hidden_proofs.append(step("question", proof, "mixed", f"Mixed set ({why} hidden in here)",
                                          {"mixed_unlabeled": True}, ticket_id=t.id))

    # 2. Rule cards.
    if block_min.get("cards"):
        steps.append({"kind": "cards", "count": min(due_cards, max(3, int(block_min["cards"] * 2))), "block": "cards",
                      "reason": f"{due_cards} rule card(s) due. Say it before you flip: recall beats rereading", "domain": ""})

    # 3. New math skill: worked examples first, then first tries.
    focus_min = block_min.get("focus", 0)
    novice = bool(focus) and section == "math" and stats.get(focus, {}).get("attempts", 0) < 3
    if novice and focus_min:
        before = len(steps)
        for _ in range(2):
            ex = pick(db, user_id, skill_id=focus, difficulty="medium", exclude=used)
            if ex:
                steps.append(step("worked", ex, "learn", "New skill: study a solved one first"))
        for _ in range(2):
            q = pick(db, user_id, skill_id=focus, difficulty="medium", exclude=used)
            if q:
                steps.append(step("question", q, "learn", "Now your turn, same kind of question"))
        # Whatever the learn steps don't use flows into the mixed set, so the session keeps its length.
        focus_min = max(0.0, focus_min - (len(steps) - before) * PER_QUESTION_MIN)

    # 4. Mixed set.
    n = max(3, round((block_min.get("mixed", 0) + focus_min) / PER_QUESTION_MIN)) if plan.minutes > 5 else 0
    n_priority = round(n * PRIORITY_SHARE)
    if only_skill:
        n_priority = n
    targets = [top[i % len(top)] for i in range(n_priority)] if top else []
    others = [s.id for s in in_section if s.id not in top] if not only_skill else []
    targets += [rng.choice(others) for _ in range(n - len(targets))] if others else []
    mixed = list(hidden_proofs)
    for sid in targets[: max(0, n - len(hidden_proofs))]:
        item = pick(db, user_id, skill_id=sid, difficulty=target_difficulty(stats.get(sid)), exclude=used)
        if item:
            mixed.append(step("question", item, "mixed", "Mixed set"))
    steps += interleave(mixed, rng)

    blocks = []
    for key, title, why in (
        ("warmup", "Re-attempts from your log", "Spaced re-attempts are where fixes stick"),
        ("cards", "Rule cards", "Quick recall of rules and your own fix lines"),
        ("learn", "New skill: worked examples", "Study solved ones first, then solve (math, while it's new)"),
        ("mixed", "Mixed set", "Mixing types feels harder. That's the point: it trains spotting which tool to use"),
    ):
        count = sum(1 for s in steps if s["block"] == key)
        if count:
            blocks.append({"key": key, "title": title, "why": why, "count": count})
    return {"section": section, "minutes": plan.minutes, "throttled": plan.throttled, "focus_skill": focus,
            "focus_reason": focus_reason(db, user_id, focus, stats, skills), "only_skill": only_skill,
            "blocks": blocks, "steps": steps}


def focus_reason(db, user_id: str, focus: str | None, stats: dict, skills: dict) -> str:
    """One sentence on why this skill, today (design guide: Home explains the choice in one sentence)."""
    if not focus:
        return ""
    from .taxonomy import MICRO_SKILLS
    t = db.scalar(select(Ticket).where(Ticket.user_id == user_id, Ticket.skill_id == focus)
                  .order_by(Ticket.created.desc()).limit(1))
    if t and t.micro_skill:
        label = next((m.label for m in MICRO_SKILLS if m.key == t.micro_skill), t.micro_skill).lower()
        return f"Last time, {label} tripped you up. Try it again in new problems."
    st = stats.get(focus)
    if st and st["attempts"] >= 4:
        return f"You've got {st['correct']} of {st['attempts']} here so far. It's your biggest gain right now."
    share = {"algebra": 35, "advanced_math": 35, "problem_solving_data_analysis": 15, "geometry_trigonometry": 15,
             "craft_and_structure": 28, "information_and_ideas": 26, "standard_english_conventions": 26,
             "expression_of_ideas": 20}.get(skills[focus].domain, 0)
    section = "Math" if skills[focus].section == "math" else "Reading and Writing"
    return f"About {share}% of {section}, and Peak hasn't seen you try it yet."


def summary(db, user_id: str, session_id: str) -> dict:
    atts = db.scalars(select(Attempt).where(Attempt.user_id == user_id, Attempt.session_id == session_id)).all()
    graded = [a for a in atts if a.correct is not None and not json.loads(a.flags or "{}").get("cold_retry")]
    tickets = db.scalars(select(Ticket).where(Ticket.origin_attempt_id.in_([a.id for a in atts]))).all() if atts else []
    open_due = db.scalar(select(func.min(Ticket.next_due)).where(Ticket.user_id == user_id, Ticket.state.in_(DUE_STATES)))
    return {
        "answered": len(graded),
        "correct": sum(1 for a in graded if a.correct),
        "sure_wrong": sum(1 for a in graded if a.confidence == "sure" and not a.correct),
        "guessed_right": sum(1 for a in graded if a.confidence == "guess" and a.correct),
        "fixes": [{"id": t.id, "cause": t.cause, "micro_skill": t.micro_skill, "rule": t.rule} for t in tickets],
        "next_due": open_due,
    }
