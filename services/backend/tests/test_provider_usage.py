"""The monthly budget is the cost-control invariant (PRD s8.6): enforced before every provider call."""
from types import SimpleNamespace

import pytest

from peak import config, provider_usage as pu
from peak.db import ProviderCall, User


class FakeClient:
    def __init__(self, input_tokens=1000, fail=False):
        self.calls = 0
        self.messages = self
        self._in, self._fail = input_tokens, fail

    def count_tokens(self, **_):
        return SimpleNamespace(input_tokens=self._in)

    def stream(self, **_):
        self.calls += 1
        outer = self

        class Ctx:
            response = SimpleNamespace(headers={})

            def __enter__(self):
                if outer._fail:
                    raise RuntimeError("boom")
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return SimpleNamespace(usage=SimpleNamespace(input_tokens=1000, output_tokens=500), stop_reason="end_turn")

        return Ctx()


KW = dict(model="claude-sonnet-5-5", max_tokens=1000, messages=[], system="s")


@pytest.fixture()
def household(db):
    db.add(User(username="p", password_hash="x", role="parent", household="h1"))
    db.commit()
    return "h1"


def test_known_rates_cost_recorded(db, household):
    call_id = pu.new_call(household, "extract")
    pu.parse_with_receipt(FakeClient(), call_id=call_id, **KW)
    db.expire_all()
    row = db.get(ProviderCall, call_id)
    assert row.state == "done" and row.usage_known
    assert row.cost_usd == pytest.approx((1000 * 2.0 + 500 * 10.0) / 1_000_000)


def test_over_budget_blocks_before_any_paid_call(db, household, monkeypatch):
    monkeypatch.setattr(config, "PEAK_COST_LIMIT_MONTH", 0.0001)
    client = FakeClient()
    call_id = pu.new_call(household, "extract")
    with pytest.raises(pu.ProviderBudgetFailure):
        pu.parse_with_receipt(client, call_id=call_id, **KW)
    assert client.calls == 0
    db.expire_all()
    row = db.get(ProviderCall, call_id)
    assert row.state == "failed" and row.usage_known and row.cost_usd == 0


def test_request_limit_blocks(db, household, monkeypatch):
    monkeypatch.setattr(config, "PEAK_REQUEST_LIMIT_MONTH", 1)
    pu.parse_with_receipt(FakeClient(), call_id=pu.new_call(household, "a"), **KW)
    client = FakeClient()
    with pytest.raises(pu.ProviderBudgetFailure, match="request limit"):
        pu.parse_with_receipt(client, call_id=pu.new_call(household, "b"), **KW)
    assert client.calls == 0


def test_failed_call_keeps_receipt_with_unknown_usage(db, household):
    call_id = pu.new_call(household, "extract")
    with pytest.raises(RuntimeError):
        pu.parse_with_receipt(FakeClient(fail=True), call_id=call_id, **KW)
    db.expire_all()
    row = db.get(ProviderCall, call_id)
    assert row.state == "failed" and not row.usage_known and row.cost_usd is None


def test_unknown_model_cost_stays_unknown(db, household):
    call_id = pu.new_call(household, "extract")
    pu.parse_with_receipt(FakeClient(), call_id=call_id, **{**KW, "model": "mystery-model"})
    db.expire_all()
    assert db.get(ProviderCall, call_id).cost_usd is None
