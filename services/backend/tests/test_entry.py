import pytest
from peak.entry import matches_key, validate_entry


@pytest.mark.parametrize("raw", ["12", "-12", "3.25", "-.5", "7/3", "-7/3", "12345", "-1234"])
def test_valid(raw):
    assert validate_entry(raw).ok


@pytest.mark.parametrize("raw,frag", [
    ("", "Enter"),
    ("1 1/2", "Mixed"),
    ("1,000", "Commas"),
    ("$5", "Commas"),
    ("50%", "Commas"),
    ("123456", "limit is 5"),
    ("-123456", "limit is 6"),
    ("1/0", "zero"),
    ("abc", "digits"),
])
def test_invalid(raw, frag):
    res = validate_entry(raw)
    assert not res.ok and frag in res.reason


def test_negative_gets_six_chars():
    assert validate_entry("-1.234").ok  # 6 chars


def test_value_equivalence():
    assert matches_key("0.5", ["1/2"])
    assert matches_key("2/4", ["1/2"])
    assert not matches_key("1 1/2", ["3/2"])
