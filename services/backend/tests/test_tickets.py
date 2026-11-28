from datetime import date, timedelta

import pytest

from peak.tickets import (
    Evidence, State, Ticket, apply_evidence, complete_repair, maintain, needs_new_item, start_repair,
)

D0 = date(2027, 1, 4)


def repaired(timing=False):
    t = Ticket("t1", origin_family_id="famA", timing_required=timing)
    return complete_repair(start_repair(t), D0)


def ev(i, days, fam, correct=True, **kw):
    return Evidence(f"a{i}", correct, D0 + timedelta(days=days), fam, **kw)


def test_happy_path_to_confirmed():
    t = repaired()
    assert t.state == State.RETRY_DUE and t.next_due == D0 + timedelta(days=2)
    t = apply_evidence(t, ev(1, 1, "famB"))
    assert t.state == State.TRANSFER_DUE and t.next_due == D0 + timedelta(days=7)
    t = apply_evidence(t, ev(2, 8, "famC", mixed_unlabeled=True))
    assert t.state == State.CONFIRMED and t.next_due == D0 + timedelta(days=21)
    assert maintain(t).state == State.MAINTAIN
    retired = apply_evidence(t, ev(3, 21, "famD"))  # the 3-week check passes: retired
    assert retired.state == State.MAINTAIN and retired.next_due is None


def test_same_family_cannot_close():
    t = repaired()
    t = apply_evidence(t, ev(1, 1, "famA"))
    assert t.state == State.RETRY_DUE and not t.counted


def test_same_day_as_repair_does_not_count():
    t = apply_evidence(repaired(), ev(1, 0, "famB"))
    assert not t.counted


def test_aided_and_repeat_exposure_ignored():
    t = repaired()
    t = apply_evidence(t, ev(1, 1, "famB", aided=True))
    t = apply_evidence(t, ev(2, 1, "famB", first_exposure=False))
    assert not t.counted


def test_double_submission_never_advances_twice():
    t = repaired()
    t = apply_evidence(t, ev(1, 1, "famB"))
    again = apply_evidence(t, ev(1, 1, "famB"))
    assert again == t or len(again.counted) == 1


def test_same_day_pair_does_not_confirm():
    t = repaired()
    t = apply_evidence(t, ev(1, 8, "famB", mixed_unlabeled=True))
    t = apply_evidence(t, ev(2, 8, "famC", mixed_unlabeled=True))
    assert t.state != State.CONFIRMED


def test_needs_delayed_mixed_set():
    t = repaired()
    t = apply_evidence(t, ev(1, 1, "famB"))
    t = apply_evidence(t, ev(2, 3, "famC", mixed_unlabeled=True))  # only 3 days out
    assert t.state == State.TRANSFER_DUE


def test_timing_required_needs_under_pace():
    t = repaired(timing=True)
    t = apply_evidence(t, ev(1, 1, "famB"))
    t = apply_evidence(t, ev(2, 8, "famC", mixed_unlabeled=True))
    assert t.state == State.TRANSFER_DUE
    t = apply_evidence(t, ev(3, 9, "famD", under_pace=True))
    assert t.state == State.CONFIRMED


def test_fresh_miss_reopens_with_reason():
    t = apply_evidence(repaired(), ev(1, 1, "famB", correct=False))
    assert t.state == State.REOPENED and "missed fresh item" in t.reopen_reason


def test_needs_new_item_when_families_exhausted():
    t = apply_evidence(repaired(), ev(1, 1, "famB"))
    assert needs_new_item(t, {"famA", "famB"})
    assert not needs_new_item(t, {"famA", "famB", "famC"})


def test_illegal_transitions():
    with pytest.raises(ValueError):
        complete_repair(Ticket("x", None), D0)
    with pytest.raises(ValueError):
        maintain(repaired())


def test_miss_at_the_three_week_check_reopens():
    t = repaired()
    t = apply_evidence(t, ev(1, 2, "famB"))
    t = apply_evidence(t, ev(2, 8, "famC", mixed_unlabeled=True))
    t = apply_evidence(t, ev(3, 21, "famD", correct=False))
    assert t.state == State.REOPENED
