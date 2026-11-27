from datetime import date

import pytest
from fsrs import Rating

from peak.benchmarks import Conditions, series_for, stall
from peak.composer import compose
from peak.diagnose import AttemptFacts, diagnose
from peak.exam import Section
from peak.priority import SkillStats, hard_unlocked, rank_skills, skill_priority, smoothed_miss_rate
from peak.srs import new_state, rating_from_behavior, review
from peak.taxonomy import Cause


def facts(**kw):
    base = dict(correct=False, confidence="unsure", section=Section.MATH, domain="advanced_math")
    base.update(kw)
    return AttemptFacts(**base)


def test_sure_wrong_is_entrenched_with_rechecks():
    d = diagnose(facts(confidence="sure", cold_retry_correct=False))
    assert d.kind == "entrenched" and d.ticket_required and d.reverify_days == (2, 7)


def test_guess_right_gets_no_credit():
    d = diagnose(facts(correct=True, confidence="guess"))
    assert d.kind == "lucky_guess" and not d.mastery_credit


def test_cold_retry_right_is_never_content_gap():
    assert diagnose(facts(cold_retry_correct=True)).cause == Cause.EXECUTION
    assert diagnose(facts(cold_retry_correct=True, requested_quantity_flag=True)).cause == Cause.REQUESTED_QUANTITY
    assert diagnose(facts(cold_retry_correct=True, elapsed_ms=200, p90_ms=100)).cause == Cause.PACING


def test_cold_retry_wrong_rw_is_distractor():
    d = diagnose(facts(section=Section.RW, domain="craft_and_structure", cold_retry_correct=False))
    assert d.cause == Cause.EVIDENCE_DISTRACTOR


def test_slow_correct_makes_fluency_ticket():
    d = diagnose(facts(correct=True, confidence="sure", elapsed_ms=200, p90_ms=100))
    assert d.kind == "slow_correct" and d.ticket_required


def test_smoothing_pulls_toward_mean():
    assert smoothed_miss_rate(0, 0, 0.3) == pytest.approx(0.3)
    assert smoothed_miss_rate(8, 8, 0.3) == pytest.approx((8 + 2.4) / 16)


def test_priority_prefers_weak_heavy_domain_and_coursework():
    a = SkillStats("s1", "advanced_math", 20, 12)
    b = SkillStats("s2", "problem_solving_data_analysis", 20, 12)
    assert skill_priority(a, 0.3, None) > skill_priority(b, 0.3, None)
    c = SkillStats("s3", "advanced_math", 20, 12, coursework_aligned=True)
    assert skill_priority(c, 0.3, None) == pytest.approx(skill_priority(a, 0.3, None) * 1.25)


def test_hard_unlock_gate():
    assert not hard_unlocked(SkillStats("s", "algebra", 12, 3, recent_medium=(True,) * 8))
    assert hard_unlocked(SkillStats("s", "algebra", 12, 3, recent_medium=(True,) * 9 + (False,) * 3))
    assert not hard_unlocked(SkillStats("s", "algebra", 12, 3, recent_medium=(True,) * 8 + (False,) * 4))


def test_rank_skills_includes_exploration_slot():
    stats = [SkillStats(f"s{i}", "algebra", 50, 10 + i) for i in range(10)] + [SkillStats("thin", "algebra", 1, 0)]
    picks = rank_skills(stats, {}, slots=5, seed=1)
    assert len(picks) == 5 and any(r.startswith("under-measured") for _, _, r in picks)


def test_composer_25_min():
    p = compose(25, due_verifications=10, due_cards=6, focus_skill="s1")
    kinds = {b.kind for b in p.blocks}
    assert kinds == {"verification", "cards", "focus", "mixed"}
    assert sum(b.minutes for b in p.blocks) <= 25.01
    assert p.deferred_verifications > 0  # backlog capped, not stacked


def test_composer_5_min_cards_only_and_throttle():
    assert [b.kind for b in compose(5, due_verifications=3, due_cards=4, focus_skill="s").blocks] == ["cards"]
    t = compose(40, due_verifications=3, due_cards=4, focus_skill="s", today=date(2027, 3, 1),
                school_tests=[date(2027, 3, 3)])
    assert t.throttled and t.minutes == 5 and t.deferred_verifications == 3


def test_composer_rejects_odd_minutes():
    with pytest.raises(ValueError):
        compose(20, due_verifications=0, due_cards=0, focus_skill=None)


def test_rating_from_behavior():
    def r(**k):
        base = dict(correct=True, confidence="sure", elapsed_ms=50, p50_ms=60, p90_ms=100)
        return rating_from_behavior(**{**base, **k})

    assert r() == Rating.Easy
    assert r(elapsed_ms=80) == Rating.Good
    assert r(elapsed_ms=150) == Rating.Hard
    assert r(confidence="guess") == Rating.Hard
    assert r(correct=False) == Rating.Again
    assert r(hinted=True) == Rating.Again


def test_fsrs_review_roundtrip():
    state, due = review(new_state(), Rating.Good)
    state2, due2 = review(state, Rating.Good, now=due)
    assert due2 > due


def test_only_clean_conditions_enter_clean_series():
    full = Conditions(True, True, True, True)
    assert series_for("bluebook", full) == "bluebook_clean"
    assert series_for("bluebook", Conditions(True, True, False, True)) == "bluebook_exposed"
    assert series_for("psat", Conditions()) == "psat"


def test_stall_rule():
    assert stall(1120, 1140, 6) and not stall(1120, 1170, 6) and not stall(1120, 1130, 3)
