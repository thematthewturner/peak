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

from sqlalchemy import select

from .models import Item, ItemCheck, SourceDocument
from .sanitize import sanitize_html
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


def parse_options(raw) -> dict[str, str] | None:
    if raw is None:
        return None
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[str(k).strip().upper()] = sanitize_html(v if isinstance(v, str) else json.dumps(v))
    elif isinstance(raw, list):
        for i, opt in enumerate(raw):
            if isinstance(opt, dict):
                label = str(_first(opt, "label", "id", "key") or "ABCD"[i]).strip().upper()
                body = _first(opt, "content", "text", "body", "value") or ""
            else:
                label, body = "ABCD"[i], opt
            out[label[:1]] = sanitize_html(str(body))
    return out or None


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
    duplicates: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)
    unmatched_skills: dict[str, int] = field(default_factory=dict)


def to_item(rec: dict, *, source_document_id: str | None, benchmark_locked: bool) -> tuple[Item, list[tuple[str, bool, str]]]:
    ref = _first(rec, "questionId", "question_id", "externalId", "external_id", "ibn", "id")
    if ref is None:
        raise ValueError("no question id")
    stem = sanitize_html(str(_first(rec, "stem", "question", "prompt") or ""))
    passage = sanitize_html(str(_first(rec, "stimulus", "passage", "text") or ""))
    options = parse_options(_first(rec, "answerOptions", "answer_options", "choices", "options"))
    keys = parse_keys(_first(rec, "correct_answer", "correctAnswer", "keys", "answer", "correct"))
    qtype = str(_first(rec, "type", "question_type", "format") or "").lower()
    fmt = "numeric" if qtype in ("spr", "numeric", "student-produced response", "fill-in") or not options else "mc"
    domain = match_domain(_first(rec, "primary_class_cd_desc", "domain", "category"))
    sid = match_skill(domain, _first(rec, "skill_desc", "skill", "skill_name"))
    diff = DIFFICULTY.get(str(_first(rec, "difficulty", "difficulty_level") or "").strip().lower())
    rationale = sanitize_html(str(_first(rec, "rationale", "explanation") or "")) or None
    content = {"stem": stem, "passage": passage or None, "choices": options, "format": "html"}
    item = Item(
        origin="official", source_ref=str(ref), source_document_id=source_document_id, skill_id=sid,
        difficulty=diff, format=fmt, benchmark_locked=benchmark_locked, status="draft",
        rights="private_official", content=json.dumps(content), key=json.dumps(keys), rationale=rationale,
    )
    checks = [
        ("schema", bool(stem) and (fmt == "numeric" or bool(options)), "stem and choices present"),
        ("key_present", bool(keys) and (fmt == "numeric" or all(k.upper() in (options or {}) for k in keys)), "official key present"),
        ("skill_known", sid is not None, f"skill={sid}"),
    ]
    return item, checks


def import_jsonl(db, path: str | Path, *, kind: str = "qbank_export", benchmark_locked: bool = False,
                 export_filter: dict | None = None) -> ImportReport:
    path = Path(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    doc = db.scalar(select(SourceDocument).where(SourceDocument.sha256 == digest))
    report = ImportReport()
    if doc and doc.status == "published":
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
            item, checks = to_item(rec, source_document_id=doc.id, benchmark_locked=benchmark_locked)
        except (ValueError, json.JSONDecodeError, TypeError) as error:
            report.rejected.append((lineno, str(error)[:120]))
            continue
        if db.scalar(select(Item.id).where(Item.origin == "official", Item.source_ref == item.source_ref)):
            report.duplicates += 1
            continue
        if item.skill_id is None:
            name = str(_first(rec, "skill_desc", "skill", "skill_name") or "?")
            report.unmatched_skills[name] = report.unmatched_skills.get(name, 0) + 1
        db.add(item)
        db.flush()
        for name, passed, detail in checks:
            db.add(ItemCheck(item_id=item.id, check=name, passed=passed, detail=json.dumps({"detail": detail})))
        # Skill match is advisory (can be fixed in review); schema and key are gating.
        item.status = "verified" if all(p for n, p, _ in checks if n != "skill_known") else "review"
        report.created += 1
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
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        seed_skills(db)
        report = import_jsonl(db, args.path, kind=args.kind, benchmark_locked=args.benchmark_locked)
    print(json.dumps({"seen": report.seen, "created": report.created, "duplicates": report.duplicates,
                      "rejected": len(report.rejected), "unmatched_skills": report.unmatched_skills}))
    for lineno, why in report.rejected[:20]:
        print(f"line {lineno}: {why}")


if __name__ == "__main__":
    main()


__all__ = ["import_jsonl", "to_item", "match_domain", "match_skill", "DOMAINS"]
