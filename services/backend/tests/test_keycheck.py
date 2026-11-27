import json
from types import SimpleNamespace

from sqlalchemy import select

from peak import config, keycheck
from peak.mathtext import to_blocks
from peak.models import Item, ItemCheck
from tests.test_items_api import make_item

DEFAULT = "ANSWER: B\nDEFENSIBLE_OTHERS: none"


class FakeLLM:
    """Scripted replies in call order. Records every prompt so tests can prove what the model was shown."""

    def __init__(self, *replies):
        self.replies, self.prompts, self.messages = list(replies), [], self

    def count_tokens(self, **_):
        return SimpleNamespace(input_tokens=500)

    def stream(self, **kw):
        self.prompts.append(kw)
        text = self.replies.pop(0) if self.replies else DEFAULT

        class Ctx:
            response = SimpleNamespace(headers={})

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                                       usage=SimpleNamespace(input_tokens=500, output_tokens=300), stop_reason="end_turn")

        return Ctx()


def run(client, **kw):
    return keycheck.run(client, workers=1, **kw)


def checks(db):
    db.expire_all()
    return list(db.scalars(select(ItemCheck).where(ItemCheck.check == "blind_solve")))


def test_agreement_passes_and_keeps_item_in_service(db):
    item = make_item(db)  # key is B
    rep = run(FakeLLM("Working...\nANSWER: B\nDEFENSIBLE_OTHERS: none"))
    assert (rep.passed, rep.disputed, rep.passed_on_retry) == (1, 0, 0)
    db.expire_all()
    assert db.get(Item, item.id).status == "verified" and checks(db)[0].passed


def test_two_disagreements_pull_the_item_with_a_visible_record(db):
    item = make_item(db)
    rep = run(FakeLLM("ANSWER: A\nDEFENSIBLE_OTHERS: none", "ANSWER: C\nDEFENSIBLE_OTHERS: none"))
    assert rep.disputed == 1
    db.expire_all()
    assert db.get(Item, item.id).status == "review"
    c = checks(db)[0]
    assert not c.passed and json.loads(c.detail) == {"first": "A", "second": "C", "others": [], "key": ["B"]}


def test_one_disagreement_then_agreement_passes(db):
    item = make_item(db)
    rep = run(FakeLLM("ANSWER: A", "ANSWER: B"))
    assert rep.passed == 1 and rep.passed_on_retry == 1
    db.expire_all()
    assert db.get(Item, item.id).status == "verified"


def test_numeric_answers_compare_by_value(db):
    make_item(db, source_ref="N1", format="numeric", key=json.dumps(["3/2"]), content=json.dumps({"stem": "<p>3x=4.5</p>"}))
    assert run(FakeLLM("ANSWER: 1.5")).passed == 1


def test_unparseable_reply_is_a_disagreement_not_a_crash(db):
    make_item(db)
    rep = run(FakeLLM("I could not decide.", "Still unsure."))
    assert rep.disputed == 1 and rep.errors == 0


def test_the_model_never_sees_the_key_or_rationale(db):
    make_item(db)  # rationale: "Divide both sides by 2."; key "B"
    client = FakeLLM()
    run(client)
    sent = json.dumps(client.prompts[0]["messages"])
    assert "Divide both sides" not in sent and "key" not in sent.lower().replace("keyboard", "")
    assert "2x = 6" in sent and "B) 3" in sent  # the question and its choices are there


def test_run_is_resumable_and_skips_finished_items(db):
    make_item(db)
    run(FakeLLM())
    client = FakeLLM()
    rep = run(client)
    assert rep.candidates == 0 and client.prompts == []


def test_budget_stop_makes_no_call_and_leaves_items_pending(db, monkeypatch):
    make_item(db)
    monkeypatch.setattr(config, "PEAK_COST_LIMIT_MONTH", 0.00001)
    client = FakeLLM()
    rep = run(client)
    assert rep.stopped and "budget" in rep.stopped.lower() and client.prompts == []
    assert checks(db) == []
    from peak.db import SessionLocal
    with SessionLocal() as s:
        assert len(keycheck.pending_ids(s, section=None, recheck=False, limit=None)) == 1  # resumes next run


def test_only_verified_official_items_are_checked(db):
    make_item(db, source_ref="A1")
    make_item(db, source_ref="A2", status="review")
    make_item(db, source_ref="A3", origin="generated")
    assert run(FakeLLM()).candidates == 1


def test_estimate_prices_without_calling_a_model(db):
    make_item(db, source_ref="E1")
    est = keycheck.estimate()
    assert est["items"] == 1 and est["estimated_usd"] > 0 and est["input_tokens"] > 250


def test_mathml_and_images_survive_the_trip_to_the_model():
    png = "data:image/png;base64,iVBORw0KGgo="
    blocks = to_blocks(f'<p>If <math><msup><mi>x</mi><mn>2</mn></msup><mo>=</mo><mfrac><mn>1</mn><mn>4</mn></mfrac></math>'
                       f' and <img src="{png}"> what is x?</p><svg viewBox="0 0 1 1"><text>Q1</text></svg>')
    text = " ".join(b["text"] for b in blocks if b["type"] == "text")
    assert "x^(2)=(1)/(4)" in text and "Q1" in text and "<svg" in text
    assert [b["type"] for b in blocks] == ["text", "image", "text"]
    assert blocks[1]["source"] == {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}


def test_parse_reply_and_matching_edge_cases():
    assert keycheck.parse_reply("blah\nANSWER: (B)\nDEFENSIBLE_OTHERS: A, C") == ("(B)", ["A", "C"])
    item = SimpleNamespace(format="mc", key='["B"]')
    assert keycheck.agrees(item, "(B)") and keycheck.agrees(item, "B) three") and not keycheck.agrees(item, "C")
    num = SimpleNamespace(format="numeric", key='["3/2", "1.5"]')
    assert keycheck.agrees(num, "$1.50") and keycheck.agrees(num, "3 / 2") and not keycheck.agrees(num, "2")
