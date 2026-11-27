import json

from sqlalchemy import select

from peak.models import Item, ItemCheck
from peak.qbank import import_jsonl, match_domain, match_skill, parse_options
from peak.sanitize import sanitize_html
from peak.seed import seed_skills

MC = {
    "questionId": "abc123", "type": "mcq", "difficulty": "H",
    "primary_class_cd_desc": "Advanced Math", "skill_desc": "Nonlinear functions",
    "stem": "<p>If <math><mi>x</mi></math> = 2, what is f(x)?</p><script>alert(1)</script>",
    "answerOptions": [{"id": "a", "content": "1"}, {"id": "b", "content": "2"}, {"id": "c", "content": "3"}, {"id": "d", "content": "4"}],
    "correct_answer": ["B"], "rationale": "<p>Because.</p>",
}
SPR = {"externalId": "spr1", "type": "spr", "difficulty": "easy", "domain": "Algebra",
       "skill": "Linear equations in one variable", "stem": "2x=3. x=?", "correct_answer": "3/2,1.5"}


def write(tmp_path, *recs, name="q.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) if isinstance(r, dict) else r for r in recs))
    return p


def test_import_mc_and_numeric(db, tmp_path):
    seed_skills(db)
    rep = import_jsonl(db, write(tmp_path, MC, SPR))
    assert rep.created == 2 and not rep.rejected
    mc = db.scalar(select(Item).where(Item.source_ref == "abc123"))
    assert mc.status == "verified" and mc.difficulty == "hard" and mc.format == "mc"
    assert mc.skill_id == "advanced_math.nonlinear-functions"
    assert "<script" not in mc.content and "alert" not in mc.content
    assert json.loads(mc.key) == ["B"]
    spr = db.scalar(select(Item).where(Item.source_ref == "spr1"))
    assert spr.format == "numeric" and json.loads(spr.key) == ["3/2", "1.5"]
    assert db.scalar(select(ItemCheck).where(ItemCheck.item_id == mc.id, ItemCheck.check == "key_present")).passed


def test_reimport_is_noop(db, tmp_path):
    seed_skills(db)
    p = write(tmp_path, MC)
    import_jsonl(db, p)
    again = import_jsonl(db, p)
    assert again.duplicates == -1 and len(db.scalars(select(Item)).all()) == 1


def test_overlapping_file_dedupes_by_question_id(db, tmp_path):
    seed_skills(db)
    import_jsonl(db, write(tmp_path, MC, name="a.jsonl"))
    rep = import_jsonl(db, write(tmp_path, MC, SPR, name="b.jsonl"))
    assert rep.duplicates == 1 and rep.created == 1


def test_bad_records_reported_not_fatal(db, tmp_path):
    seed_skills(db)
    rep = import_jsonl(db, write(tmp_path, "not json", {"stem": "no id"}, MC))
    assert rep.created == 1 and len(rep.rejected) == 2


def test_missing_key_goes_to_review_and_is_not_served(db, tmp_path):
    seed_skills(db)
    bad = {**MC, "questionId": "nokey", "correct_answer": None}
    import_jsonl(db, write(tmp_path, bad))
    assert db.scalar(select(Item).where(Item.source_ref == "nokey")).status == "review"


def test_benchmark_locked_flag(db, tmp_path):
    seed_skills(db)
    import_jsonl(db, write(tmp_path, MC), kind="practice_test", benchmark_locked=True)
    assert db.scalar(select(Item)).benchmark_locked is True


def test_unmatched_skill_reported(db, tmp_path):
    seed_skills(db)
    rep = import_jsonl(db, write(tmp_path, {**MC, "skill_desc": "Mystery skill"}))
    assert rep.unmatched_skills == {"Mystery skill": 1}


def test_matchers():
    assert match_domain("Problem-Solving and Data Analysis") == "problem_solving_data_analysis"
    assert match_skill("algebra", "Linear functions") == "algebra.linear-functions"
    assert parse_options({"A": "x", "B": "y"}) == {"A": "x", "B": "y"}


def test_sanitizer_blocks_active_content():
    out = sanitize_html('<p onclick="x()">hi<img src="http://evil/x.png" alt="a"><iframe src=x></iframe></p><a href="javascript:1">l</a>')
    assert "onclick" not in out and "evil" not in out and "iframe" not in out and "javascript" not in out
    assert sanitize_html("<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>").startswith("<math><mfrac>")


# Real export shape: metadata at the top level, content nested under `detail`.
def nested(qid="f1bfbed3", detail=None, **top):
    d = {"type": "mcq", "stem": "<p>Which choice most logically completes the text?</p>",
         "stimulus": "<p>A passage.</p>",
         "answerOptions": [{"id": "x1", "content": "one"}, {"id": "x2", "content": "two"},
                           {"id": "x3", "content": "three"}, {"id": "x4", "content": "four"}],
         "correct_answer": ["B"], "rationale": "<p>Choice B is best.</p>"}
    d.update(detail or {})
    rec = {"questionId": qid, "skill_cd": "INF", "skill_desc": "Inferences", "primary_class_cd": "INI",
           "primary_class_cd_desc": "Information and Ideas", "difficulty": "H", "ibn": "None",
           "section": "Reading and Writing", "detail": d}
    rec.update(top)
    return rec


def test_nested_detail_dict_imports_as_verified(db, tmp_path):
    seed_skills(db)
    rep = import_jsonl(db, write(tmp_path, nested()))
    item = db.scalar(select(Item))
    assert rep.created == 1 and item.status == "verified" and item.format == "mc"
    assert item.difficulty == "hard" and item.skill_id == "information_and_ideas.inferences"
    assert json.loads(item.key) == ["B"] and "Choice B" in item.rationale


def test_nested_detail_as_json_string(db, tmp_path):
    seed_skills(db)
    rec = nested()
    rec["detail"] = json.dumps(rec["detail"])
    import_jsonl(db, write(tmp_path, rec))
    assert db.scalar(select(Item)).status == "verified"


def test_choice_labels_fall_back_to_positions_when_ids_are_opaque(db, tmp_path):
    seed_skills(db)
    import_jsonl(db, write(tmp_path, nested()))
    choices = json.loads(db.scalar(select(Item)).content)["choices"]
    assert list(choices) == ["A", "B", "C", "D"] and choices["B"] == "two"


def test_item_with_figure_is_held_for_review_not_served(db, tmp_path):
    seed_skills(db)
    rec = nested(detail={"stem": '<p>See graph.</p><img src="https://cdn.example/fig.png" alt="g">'})
    rep = import_jsonl(db, write(tmp_path, rec))
    assert db.scalar(select(Item)).status == "review" and rep.check_failures == {"figure": 1}


def test_misread_export_aborts_and_saves_nothing(db, tmp_path):
    seed_skills(db)
    junk = [{"questionId": f"id{i}", "difficulty": "H", "skill_desc": "Inferences",
             "primary_class_cd_desc": "Information and Ideas", "detail": {"unknown_field": "x"}} for i in range(12)]
    p = write(tmp_path, *junk)
    rep = import_jsonl(db, p)
    assert rep.aborted and "not understood" in rep.aborted and "unknown_field" in rep.aborted
    assert db.scalar(select(Item)) is None  # rolled back
    # The file is not marked published, so re-running after a fix works without a manual reset.
    good = write(tmp_path, *[nested(qid=f"ok{i}") for i in range(12)], name="good.jsonl")
    again = import_jsonl(db, good)
    assert again.aborted is None and again.verified == 12


def test_answer_key_given_as_option_id_resolves_to_letter(db, tmp_path):
    seed_skills(db)
    import_jsonl(db, write(tmp_path, nested(detail={"correct_answer": ["x3"]})))
    assert json.loads(db.scalar(select(Item)).key) == ["C"]
    assert db.scalar(select(Item)).status == "verified"


def test_numeric_nested_record(db, tmp_path):
    seed_skills(db)
    rec = nested(detail={"type": "spr", "answerOptions": None, "correct_answer": ["3/2", "1.5"], "stimulus": None},
                 skill_desc="Linear equations in one variable", primary_class_cd_desc="Algebra", difficulty="E")
    import_jsonl(db, write(tmp_path, rec))
    item = db.scalar(select(Item))
    assert item.format == "numeric" and item.status == "verified" and item.difficulty == "easy"
