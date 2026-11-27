"""Import official Question Bank exports (JSONL) into the private item bank (PRD s8.3).

The importer is deliberately tolerant about field names: exports differ by how they were
downloaded. Unknown shapes fail loudly per record (collected in the report), never silently.
Items import as verified only if deterministic checks pass (schema, key present, known skill).
The model blind-solve and SymPy checks run later as worker jobs and may pull an item.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select

from .models import Attempt, Item, ItemCheck, SourceDocument
from .sanitize import is_safe_src, sanitize_html
from .taxonomy import DOMAINS, OFFICIAL_SKILLS, skill_id

DOMAIN_ALIASES = {
    "craft and structure": "craft_and_structure",
    "information and ideas": "information_and_ideas",
    "standard english conventions": "standard_english_conventions",
    "expression of ideas": "expression_of_ideas",
    "algebra": "algebra",
    "advanced math": "advanced_math",
    "problem-solving and data analysis": "problem_solving_data_analysis",
    "problem solving and data analysis": "problem_solving_data_analysis",
    "geometry and trigonometry": "geometry_trigonometry",
}
DIFFICULTY = {"e": "easy", "easy": "easy", "m": "medium", "medium": "medium", "h": "hard", "hard": "hard",
              "1": "easy", "2": "medium", "3": "hard"}


def _first(rec: dict, *names):
    for n in names:
        if n in rec and rec[n] not in (None, "", []):
            return rec[n]
    return None


LEGACY_KEY_FIELDS = ("correct_choice", "correctChoice", "correct", "correct_answer", "correctAnswer", "answer", "key", "keys", "answers", "value")
LEGACY_RATIONALE_FIELDS = ("rationale", "explanation", "solution")
LEGACY_CORRECT_FLAGS = ("correct", "is_correct", "isCorrect")


def _as_dict(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            try:
                import ast
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return None
    return value if isinstance(value, dict) else None


def legacy_to_modern(item: dict) -> dict:
    """Older exports wrap the question in a one-item list: {item_id, section, prompt|body, answer{style,
    choices{a:{body}}, ...}}. Rewrite it into the modern shape the rest of the importer reads."""
    answer = _as_dict(item.get("answer")) or {}
    out: dict = {"stem": _first(item, "prompt", "body", "stem"), "stimulus": _first(item, "stimulus", "passage")}
    style = str(answer.get("style") or item.get("style") or "").lower()
    choices = _as_dict(answer.get("choices")) or {}
    flagged = []
    if choices:
        options = []
        for label, choice in choices.items():
            if isinstance(choice, dict):
                options.append({"id": label, "content": _first(choice, "body", "content", "text") or ""})
                if any(choice.get(f) is True for f in LEGACY_CORRECT_FLAGS):
                    flagged.append(str(label))
            else:
                options.append({"id": label, "content": str(choice)})
        out["answerOptions"] = options
    numeric = bool(style) and "multiple" not in style
    out["type"] = "spr" if numeric or not choices else "mcq"
    key = flagged or next((answer[f] for f in LEGACY_KEY_FIELDS if answer.get(f) not in (None, "", [])), None)
    if key is None:
        key = next((item[f] for f in LEGACY_KEY_FIELDS if item.get(f) not in (None, "", [])), None)
    out["correct_answer"] = key
    out["rationale"] = (next((answer[f] for f in LEGACY_RATIONALE_FIELDS if answer.get(f)), None)
                        or next((item[f] for f in LEGACY_RATIONALE_FIELDS if item.get(f)), None))
    return out


def flatten(rec: dict) -> dict:
    """Real exports keep question content under `detail` (a dict or a JSON string) and metadata at the
    top level. Merge them; top-level metadata wins on conflicts."""
    detail = rec.get("detail")
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        detail = legacy_to_modern(detail[0])
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except ValueError:
            detail = None
    if not isinstance(detail, dict):
        return rec
    return {**detail, **{k: v for k, v in rec.items() if k != "detail"}}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def match_domain(name: str | None) -> str | None:
    n = _norm(name or "")
    for alias, key in DOMAIN_ALIASES.items():
        if _norm(alias) == n:
            return key
    return None


def match_skill(domain: str | None, name: str | None) -> str | None:
    if not domain or not name:
        return None
    n = _norm(name)
    for official in OFFICIAL_SKILLS[domain]:
        o = _norm(official)
        if o == n or o.startswith(n) or n.startswith(o):
            return skill_id(domain, official)
    return None


LETTERS = "ABCDEFGH"


def parse_options_ex(raw) -> tuple[dict[str, str] | None, dict[str, str]]:
    """Return (label -> sanitized html, original id -> label).

    Use the export's own labels when they are clean letters; otherwise (opaque ids such as UUIDs)
    label by position A, B, C, D. The id map lets a key given as an id still resolve to a letter."""
    if raw is None:
        return None, {}
    pairs: list[tuple[str, str]] = []  # (original id or "", html)
    if isinstance(raw, dict):
        pairs = [(str(k).strip(), v if isinstance(v, str) else json.dumps(v)) for k, v in raw.items()]
    elif isinstance(raw, list):
        for opt in raw:
            if isinstance(opt, dict):
                pairs.append((str(_first(opt, "label", "id", "key") or "").strip(),
                              str(_first(opt, "content", "text", "body", "value") or "")))
            else:
                pairs.append(("", str(opt)))
    if not pairs:
        return None, {}
    ids = [i.upper() for i, _ in pairs]
    clean = len(set(ids)) == len(ids) and all(i in LETTERS for i in ids)
    labels = ids if clean else list(LETTERS[: len(pairs)])
    options = {lab: sanitize_html(html) for lab, (_, html) in zip(labels, pairs)}
    idmap = {orig: lab for lab, (orig, _) in zip(labels, pairs) if orig}
    return options, idmap


def parse_options(raw) -> dict[str, str] | None:
    return parse_options_ex(raw)[0]


def parse_keys(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [p.strip() for p in re.split(r"[,;|]", str(raw)) if p.strip()]


@dataclass
class ImportReport:
    seen: int = 0
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)
    unmatched_skills: dict[str, int] = field(default_factory=dict)
    verified: int = 0
    understood: int = 0  # stem and answer key were both read: the format is understood, whatever else holds an item
    check_failures: dict[str, int] = field(default_factory=dict)
    detail_keys: dict[str, int] = field(default_factory=dict)
    legacy_keys: dict[str, int] = field(default_factory=dict)
    aborted: str | None = None


IMG_TAG = re.compile(r"<\s*img\b[^>]*>", re.I)
IMG_SRC = re.compile(r"""\bsrc\s*=\s*(["'])(.*?)\1""", re.I | re.S)
ACTIVE = re.compile(r"<\s*(object|embed|iframe)\b", re.I)


def _strings(obj):
    """Every string inside a nested option structure (json.dumps would escape the quotes we must inspect)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def needs_unstored_figure(*raw: str) -> bool:
    """True only if the item has an image the sanitizer would drop (remote URL, SVG, object/embed).
    Inline raster images (data:image/png etc.) are kept as they are, so they do not hold an item."""
    for text in raw:
        if ACTIVE.search(text):
            return True
        for tag in IMG_TAG.findall(text):
            m = IMG_SRC.search(tag)
            if not m or not is_safe_src(m.group(2)):
                return True
    return False


def to_item(rec: dict, *, source_document_id: str | None, benchmark_locked: bool) -> tuple[Item, list[tuple[str, bool, str]]]:
    rec = flatten(rec)
    ref = _first(rec, "questionId", "question_id", "externalId", "external_id", "ibn", "id")
    if ref is None:
        raise ValueError("no question id")
    raw_stem = str(_first(rec, "stem", "question", "prompt") or "")
    raw_passage = str(_first(rec, "stimulus", "passage", "text") or "")
    raw_options = _first(rec, "answerOptions", "answer_options", "choices", "options")
    stem = sanitize_html(raw_stem)
    passage = sanitize_html(raw_passage)
    options, idmap = parse_options_ex(raw_options)
    # Images/SVG are not stored yet (figures must be private assets, PRD s8.3), so an item that needs
    # one would render incomplete. Flag it and hold it out of service rather than serve a broken question.
    needs_figure = needs_unstored_figure(raw_stem, raw_passage, *_strings(raw_options))
    # An inline SVG is kept by the sanitizer; if sanitizing removed it entirely the figure is lost: hold.
    raw_all = (raw_stem + raw_passage + " ".join(_strings(raw_options))).lower()
    clean_all = (stem + passage + " ".join((options or {}).values())).lower()
    needs_figure = needs_figure or ("<svg" in raw_all and "<svg" not in clean_all)
    keys = parse_keys(_first(rec, "correct_answer", "correctAnswer", "keys", "answer", "correct"))
    if options:  # a key may be given as an option id rather than a letter
        keys = [idmap.get(k, k.upper() if k.upper() in options else k) for k in keys]
    qtype = str(_first(rec, "type", "question_type", "format") or "").lower()
    fmt = "numeric" if qtype in ("spr", "numeric", "student-produced response", "fill-in") or not options else "mc"
    domain = match_domain(_first(rec, "primary_class_cd_desc", "domain", "category"))
    sid = match_skill(domain, _first(rec, "skill_desc", "skill", "skill_name"))
    diff = DIFFICULTY.get(str(_first(rec, "difficulty", "difficulty_level") or "").strip().lower())
    rationale = sanitize_html(str(_first(rec, "rationale", "explanation") or "")) or None
    content = {"stem": stem, "passage": passage or None, "choices": options, "format": "html", "needs_figure": needs_figure}
    # Items generated from one template/cluster share a family: a repair is only proven on a different one.
    fam = next((str(rec[k]) for k in ("templateclusterid", "parenttemplateid", "templateid")
                if rec.get(k) not in (None, "", "None")), None)
    item = Item(
        origin="official", source_ref=str(ref), family_id=f"qb:{fam}" if fam else None, source_document_id=source_document_id, skill_id=sid,
        difficulty=diff, format=fmt, benchmark_locked=benchmark_locked, status="draft",
        rights="private_official", content=json.dumps(content), key=json.dumps(keys), rationale=rationale,
    )
    checks = [
        ("schema", bool(stem) and (fmt == "numeric" or bool(options)), "stem and choices present"),
        ("key_present", bool(keys) and (fmt == "numeric" or all(k.upper() in (options or {}) for k in keys)), "official key present"),
        ("skill_known", sid is not None, f"skill={sid}"),
        ("figure", not needs_figure, "item contains an image/figure that is not stored yet" if needs_figure else "no figure"),
    ]
    return item, checks


def _record_checks(db, item, checks, report) -> None:
    for name, passed, detail in checks:
        db.add(ItemCheck(item_id=item.id, check=name, passed=passed, detail=json.dumps({"detail": detail})))
    # Skill match is advisory (can be fixed in review); schema, key and figure are gating.
    item.status = "verified" if all(p for n, p, _ in checks if n != "skill_known") else "review"
    report.understood += all(p for n, p, _ in checks if n in ("schema", "key_present"))


IMPORT_CHECKS = ("schema", "key_present", "skill_known", "figure")  # owned by the importer; others (blind_solve) are not


def _key_disputed(db, item_id) -> bool:
    """A blind solve disagreed with the official key twice: the item stays out of service until a human decides."""
    return bool(db.scalar(select(ItemCheck.id).where(ItemCheck.item_id == item_id, ItemCheck.check == "blind_solve",
                                                     ItemCheck.passed.is_(False))))


def _refresh(db, existing, fresh, checks, report) -> bool:
    """Re-import of a known Question ID. Returns True if the stored item changed.

    A re-fetched export can fill in content that was missing, and an improved importer can add
    metadata. An item a student has already attempted keeps its content and key (attempts reference
    them); only a missing family id is filled in."""
    attempted = db.scalar(select(func.count()).select_from(Attempt).where(Attempt.item_id == existing.id))
    if attempted:
        if existing.family_id is None and fresh.family_id:
            existing.family_id = fresh.family_id
            return True
        return False
    fresh_ok = all(passed for name, passed, _ in checks if name != "skill_known")
    if existing.status == "verified" and not fresh_ok:
        return False  # never let a worse export downgrade a verified item
    fields = ("skill_id", "family_id", "difficulty", "format", "benchmark_locked", "content", "key", "rationale")
    disputed = _key_disputed(db, existing.id) and (existing.content, existing.key) == (fresh.content, fresh.key)
    fresh_status = "verified" if fresh_ok and not disputed else "review"
    # Status counts as a change: an item held by an older, stricter rule must be re-evaluated even when
    # its stored content already matches the export.
    changed = existing.status != fresh_status or any(getattr(existing, f) != getattr(fresh, f) for f in fields)
    if not changed:
        return False
    stale = ["blind_solve"] if (existing.content, existing.key) != (fresh.content, fresh.key) else []
    if stale:
        existing.version += 1  # content or key changed: an earlier blind solve no longer applies
    for f in fields:
        setattr(existing, f, getattr(fresh, f))
    db.query(ItemCheck).filter(ItemCheck.item_id == existing.id, ItemCheck.check.in_(list(IMPORT_CHECKS) + stale)).delete(
        synchronize_session=False)
    _record_checks(db, existing, checks, report)
    if _key_disputed(db, existing.id):
        existing.status = "review"
    report.verified += existing.status == "verified"
    return True


MIN_USABLE_RATIO = 0.5  # below this, the export shape is not understood: abort instead of reporting success


def import_jsonl(db, path: str | Path, *, kind: str = "qbank_export", benchmark_locked: bool = False,
                 export_filter: dict | None = None, min_usable_ratio: float = MIN_USABLE_RATIO,
                 reprocess: bool = False) -> ImportReport:
    path = Path(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    doc = db.scalar(select(SourceDocument).where(SourceDocument.sha256 == digest))
    report = ImportReport()
    if doc and doc.status == "published" and not reprocess:
        report.duplicates = -1  # whole file already ingested: re-upload is a no-op
        return report
    if not doc:
        doc = SourceDocument(sha256=digest, kind=kind, path=str(path), export_filter_json=json.dumps(export_filter or {}))
        db.add(doc)
        db.flush()
    for lineno, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        report.seen += 1
        try:
            rec = json.loads(line)
            if isinstance(rec, dict) and isinstance(rec.get("detail"), list) and rec["detail"] and isinstance(rec["detail"][0], dict):
                first = rec["detail"][0]
                for k in first:
                    report.legacy_keys[f"item.{k}"] = report.legacy_keys.get(f"item.{k}", 0) + 1
                for k in (_as_dict(first.get("answer")) or {}):
                    report.legacy_keys[f"answer.{k}"] = report.legacy_keys.get(f"answer.{k}", 0) + 1
            for key in (flatten(rec) if isinstance(rec, dict) and isinstance(rec.get("detail"), (dict, str)) else {}):
                if key not in rec:
                    report.detail_keys[key] = report.detail_keys.get(key, 0) + 1
            item, checks = to_item(rec, source_document_id=doc.id, benchmark_locked=benchmark_locked)
        except (ValueError, json.JSONDecodeError, TypeError) as error:
            report.rejected.append((lineno, str(error)[:120]))
            continue
        for name, passed, _ in checks:  # report every item's failures, changed or not, so holds are never hidden
            if not passed and name != "skill_known":
                report.check_failures[name] = report.check_failures.get(name, 0) + 1
        existing = db.scalar(select(Item).where(Item.origin == "official", Item.source_ref == item.source_ref))
        if existing is not None:
            if _refresh(db, existing, item, checks, report):
                report.updated += 1
            else:
                report.duplicates += 1
            continue
        if item.skill_id is None:
            name = str(_first(rec, "skill_desc", "skill", "skill_name") or "?")
            report.unmatched_skills[name] = report.unmatched_skills.get(name, 0) + 1
        db.add(item)
        db.flush()
        _record_checks(db, item, checks, report)
        report.verified += item.status == "verified"
        report.created += 1
    processed = report.created + report.updated
    # Abort only when stems/keys can't be read (a misread format). Items held for another reason, such as
    # a figure, are legitimate and must not trigger a rollback.
    if processed >= 10 and report.understood / processed < min_usable_ratio:
        # Most items unusable means the export shape was misread. Do not publish half-garbage.
        db.rollback()
        report.aborted = (
            f"only {report.understood}/{processed} items had a readable stem and answer key; the export format is not understood. "
            f"failed checks: {report.check_failures}; content fields seen: {sorted(report.detail_keys)}"
        )
        return report
    doc.status = "published"
    db.commit()
    return report


def main(argv=None):
    import argparse

    from .db import SessionLocal
    from .seed import seed_skills

    parser = argparse.ArgumentParser(description="Import a Question Bank JSONL export (private corpus)")
    parser.add_argument("path")
    parser.add_argument("--kind", default="qbank_export")
    parser.add_argument("--benchmark-locked", action="store_true")
    parser.add_argument("--reprocess", action="store_true",
                        help="re-run an already imported file (e.g. after an importer upgrade); updates items in place")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        seed_skills(db)
        report = import_jsonl(db, args.path, kind=args.kind, benchmark_locked=args.benchmark_locked, reprocess=args.reprocess)
    print(json.dumps({"seen": report.seen, "created": report.created, "updated": report.updated, "verified": report.verified,
                      "duplicates": report.duplicates, "rejected": len(report.rejected),
                      "check_failures": report.check_failures, "unmatched_skills": report.unmatched_skills,
                      "content_fields": report.detail_keys,
                      "legacy_fields": report.legacy_keys}))
    for lineno, why in report.rejected[:20]:
        print(f"line {lineno}: {why}")
    if report.aborted:
        raise SystemExit(f"IMPORT ABORTED, nothing saved: {report.aborted}")


if __name__ == "__main__":
    main()


__all__ = ["import_jsonl", "to_item", "match_domain", "match_skill", "DOMAINS"]
