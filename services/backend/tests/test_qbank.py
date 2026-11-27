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


def test_family_from_template_fields(db, tmp_path):
    seed_skills(db)
    recs = [nested("c1", templateclusterid="CL9", parenttemplateid="P1"),
            nested("p1", parenttemplateid="P1"),
            nested("t1", templateid="T7"),
            nested("n1")]
    import_jsonl(db, write(tmp_path, *recs))
    fam = {i.source_ref: i.family_id for i in db.scalars(select(Item))}
    assert fam == {"c1": "qb:CL9", "p1": "qb:P1", "t1": "qb:T7", "n1": None}


def test_refetch_fills_in_missing_content_in_place(db, tmp_path):
    seed_skills(db)
    stub = {k: v for k, v in nested("miss1").items() if k != "detail"}  # crawler failed: metadata only
    first = import_jsonl(db, write(tmp_path, stub, name="a.jsonl"))
    item = db.scalar(select(Item))
    assert item.status == "review" and first.verified == 0
    again = import_jsonl(db, write(tmp_path, nested("miss1"), name="b.jsonl"))
    db.expire_all()
    item = db.scalar(select(Item))
    assert again.updated == 1 and again.created == 0 and item.status == "verified"
    assert len(db.scalars(select(Item)).all()) == 1 and item.version == 2


def test_reprocess_same_file_backfills_family(db, tmp_path):
    seed_skills(db)
    p = write(tmp_path, nested("r1", templateclusterid="CL1"))
    import_jsonl(db, p)
    item = db.scalar(select(Item))
    item.family_id = None
    db.commit()
    assert import_jsonl(db, p).duplicates == -1  # without the flag the file is skipped
    rep = import_jsonl(db, p, reprocess=True)
    db.expire_all()
    assert rep.updated == 1 and db.scalar(select(Item)).family_id == "qb:CL1"


def test_verified_item_is_never_downgraded_by_a_worse_export(db, tmp_path):
    seed_skills(db)
    import_jsonl(db, write(tmp_path, nested("keep"), name="a.jsonl"))
    stub = {k: v for k, v in nested("keep").items() if k != "detail"}
    import_jsonl(db, write(tmp_path, stub, name="b.jsonl"))
    db.expire_all()
    item = db.scalar(select(Item))
    assert item.status == "verified" and "Choice B" in item.rationale


def test_attempted_item_keeps_content_and_key(db, tmp_path):
    from peak.db import User
    from peak.models import Attempt
    seed_skills(db)
    import_jsonl(db, write(tmp_path, nested("att"), name="a.jsonl"))
    item = db.scalar(select(Item))
    db.add(User(id="u1", username="u", password_hash="x", role="student"))
    db.commit()
    db.add(Attempt(user_id="u1", item_id=item.id, answer="A", correct=False, idempotency_key="k-1"))
    db.commit()
    changed = nested("att", detail={"correct_answer": ["D"], "rationale": "different"}, templateclusterid="CL3")
    import_jsonl(db, write(tmp_path, changed, name="b.jsonl"))
    db.expire_all()
    item = db.scalar(select(Item))
    assert json.loads(item.key) == ["B"] and "Choice B" in item.rationale  # unchanged under attempts
    assert item.family_id == "qb:CL3"  # but the missing family is filled in


def legacy(qid="leg1", answer=None, **item):
    a = {"style": "Multiple Choice",
         "choices": {"a": {"body": '<p class="choice_paragraph ">2</p>\n'}, "b": {"body": "<p>3</p>"},
                     "c": {"body": "<p>4</p>"}, "d": {"body": "<p>5</p>"}},
         "correct_choice": "b", "rationale": "<p>Because 3.</p>"}
    a.update(answer or {})
    it = {"item_id": "022222-DC", "section": "Math", "prompt": '<p class="stem_paragraph ">A helicopter delivers packages. How many?</p>',
          "answer": a}
    it.update(item)
    return {"questionId": qid, "skill_desc": "Linear inequalities in one or two variables",
            "primary_class_cd_desc": "Algebra", "difficulty": "M", "ibn": "022222-DC", "external_id": "None",
            "section": "Math", "detail": [it]}


def test_legacy_list_shape_multiple_choice(db, tmp_path):
    seed_skills(db)
    rep = import_jsonl(db, write(tmp_path, legacy()))
    item = db.scalar(select(Item))
    assert rep.verified == 1 and item.status == "verified" and item.format == "mc"
    assert list(json.loads(item.content)["choices"]) == ["A", "B", "C", "D"]
    assert json.loads(item.key) == ["B"] and "Because 3" in item.rationale
    assert item.skill_id == "algebra.linear-inequalities-in-one-or-two-variables"
    assert rep.legacy_keys["answer.correct_choice"] == 1 and rep.legacy_keys["item.prompt"] == 1


def test_legacy_body_field_for_stem_and_per_choice_correct_flag(db, tmp_path):
    seed_skills(db)
    rec = legacy("leg2", answer={"correct_choice": None, "choices": {
        "a": {"body": "<p>x</p>"}, "b": {"body": "<p>y</p>", "correct": True}, "c": {"body": "<p>z</p>"}, "d": {"body": "<p>w</p>"}}})
    rec["detail"][0].pop("prompt")
    rec["detail"][0]["body"] = "<div>Stem in body</div>"
    import_jsonl(db, write(tmp_path, rec))
    item = db.scalar(select(Item))
    assert item.status == "verified" and json.loads(item.key) == ["B"] and "Stem in body" in item.content


def test_legacy_answer_as_python_repr_string(db, tmp_path):
    seed_skills(db)
    rec = legacy("leg3")
    rec["detail"][0]["answer"] = str(rec["detail"][0]["answer"])  # str(dict) with single quotes
    import_jsonl(db, write(tmp_path, rec))
    assert db.scalar(select(Item)).status == "verified"


def test_legacy_numeric_style(db, tmp_path):
    seed_skills(db)
    rec = legacy("leg4", answer={"style": "Student-Produced Response", "choices": None, "correct_choice": None,
                                 "correct_answer": "3/2"})
    import_jsonl(db, write(tmp_path, rec))
    item = db.scalar(select(Item))
    assert item.format == "numeric" and json.loads(item.key) == ["3/2"] and item.status == "verified"


def test_legacy_with_unknown_key_field_is_held_and_visible(db, tmp_path):
    seed_skills(db)
    rec = legacy("leg5", answer={"correct_choice": None, "mystery_field": "b"})
    rep = import_jsonl(db, write(tmp_path, rec))
    assert db.scalar(select(Item)).status == "review" and rep.check_failures.get("key_present") == 1
    assert "answer.mystery_field" in rep.legacy_keys  # the report tells us what the real field is called


def test_figure_held_items_do_not_trigger_the_abort_guard(db, tmp_path):
    seed_skills(db)
    figs = [nested(f"fg{i}", detail={"stem": f'<p>See graph {i}.</p><img src="https://cdn.example/{i}.png">'}) for i in range(12)]
    rep = import_jsonl(db, write(tmp_path, *figs))
    assert rep.aborted is None and rep.understood == 12 and rep.verified == 0
    assert {i.status for i in db.scalars(select(Item))} == {"review"}  # held, but saved and counted


PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAHn3o4wAAAABJRU5ErkJggg=="


def test_inline_png_images_are_kept_and_do_not_hold_the_item(db, tmp_path):
    seed_skills(db)
    rec = nested("img1", detail={
        "stem": f'<p>Evaluate <img src="{PNG}" alt="x squared"> now.</p>',
        "answerOptions": [{"id": "a", "content": f'<img src="{PNG}">'}, {"id": "b", "content": "2"},
                          {"id": "c", "content": "3"}, {"id": "d", "content": "4"}]})
    rep = import_jsonl(db, write(tmp_path, rec))
    item = db.scalar(select(Item))
    assert item.status == "verified" and not rep.check_failures
    assert "data:image/png;base64" in item.content  # the image survived sanitization


def test_remote_svg_and_object_figures_are_held(db, tmp_path):
    seed_skills(db)
    recs = [nested("f1", detail={"stem": '<p>x</p><img src="https://cdn.example/a.png">'}),
            nested("f2", detail={"stem": '<p>x</p><svg><circle/></svg>'}),
            nested("f3", detail={"stem": '<p>x</p><img src="data:image/svg+xml;base64,PHN2Zz4=">'}),
            nested("f4", detail={"stem": '<p>x</p><img alt="no src">'})]
    rep = import_jsonl(db, write(tmp_path, *recs))
    assert rep.check_failures == {"figure": 4} and rep.verified == 0


def test_reprocess_re_evaluates_a_stale_status_even_when_content_is_unchanged(db, tmp_path):
    seed_skills(db)
    p = write(tmp_path, nested("stale"))
    import_jsonl(db, p)
    item = db.scalar(select(Item))
    item.status = "review"  # e.g. held by an older, stricter rule; stored content already matches the export
    db.commit()
    rep = import_jsonl(db, p, reprocess=True)
    db.expire_all()
    assert rep.updated == 1 and db.scalar(select(Item)).status == "verified"
