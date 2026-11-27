import pytest
from peak.exam import DOMAIN_SHARES, MODULES, Section
from peak.taxonomy import DOMAINS, MICRO_SKILLS


def test_domain_shares_sum_to_one_per_section():
    for sec in Section:
        total = sum(d.share for d in DOMAINS if d.section == sec)
        assert total == pytest.approx(1.0)


def test_every_domain_has_share():
    assert {d.key for d in DOMAINS} == set(DOMAIN_SHARES)


def test_micro_skill_keys_unique():
    keys = [m.key for m in MICRO_SKILLS]
    assert len(keys) == len(set(keys))


def test_module_timing_matches_prd():
    assert round(MODULES[Section.RW].seconds_per_item) == 71
    assert round(MODULES[Section.MATH].seconds_per_item) == 95
