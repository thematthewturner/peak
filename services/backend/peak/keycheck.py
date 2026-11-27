"""Blind-solve key verification (PRD s8.3, s8.6).

A model solves each official item WITHOUT the answer key or rationale. If it agrees with the official key, the
item passes. If it disagrees, it solves once more; only two disagreements pull the item (status review, with a
failed blind_solve check) for a human decision. The official key stays the ground truth: a disagreement is a
flag, never an automatic correction.

Spend is metered through parse_with_receipt, so PEAK_COST_LIMIT_MONTH applies. Run `--estimate` first.

  python -m peak.keycheck --estimate [--section math]
  python -m peak.keycheck [--limit N] [--section math|rw] [--workers 4] [--model ID] [--recheck]
"""
from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction

from sqlalchemy import select

from . import config, logs, provider_keys
from .db import SessionLocal
from .mathtext import to_blocks
from .models import Item, ItemCheck, Skill
from .provider_usage import ProviderBudgetFailure, model_rates, new_call, parse_with_receipt

log = logging.getLogger("peak.keycheck")

SYSTEM = (
    "You are an expert SAT tutor independently solving one Digital SAT question. Work through it carefully, "
    "check your result, then finish with exactly these two lines and nothing after them:\n"
    "ANSWER: <the letter of the best choice, or the exact number for a student-produced response>\n"
    "DEFENSIBLE_OTHERS: <letters of any other choice you consider defensible, or none>"
)
LETTERS = "ABCDEFGH"
OUTPUT_TOKENS_ASSUMED = {"math": 1500, "rw": 700}  # rough planning figure for --estimate, not a measurement
MAX_TOKENS = {"math": 4000, "rw": 2000}


def _content(raw: str):
    return json.loads(raw or "{}")


def build_messages(item: Item, section: str) -> list[dict]:
    """The model sees the question, passage and choices. Never the key or rationale."""
    c = _content(item.content)
    blocks: list[dict] = []
    if c.get("passage"):
        blocks += [{"type": "text", "text": "PASSAGE:"}] + to_blocks(c["passage"])
    blocks += [{"type": "text", "text": "QUESTION:"}] + to_blocks(c.get("stem") or "")
    if item.format == "mc" and c.get("choices"):
        for label, html in c["choices"].items():
            body = to_blocks(html) or [{"type": "text", "text": ""}]
            if body[0]["type"] == "text":
                body[0] = {"type": "text", "text": f"{label}) {body[0]['text']}"}
            else:
                body.insert(0, {"type": "text", "text": f"{label})"})
            blocks += body
    else:
        blocks.append({"type": "text", "text": "This is a student-produced response. Give the exact numeric answer "
                                              "(a fraction such as 3/2, or a decimal)."})
    return [{"role": "user", "content": [b for b in blocks if b["type"] != "text" or b["text"].strip()]}]


def parse_reply(text: str) -> tuple[str | None, list[str]]:
    answers = re.findall(r"(?im)^\W*ANSWER:\s*(.+?)\s*$", text or "")
    others = re.findall(r"(?im)^\W*DEFENSIBLE_OTHERS:\s*(.+?)\s*$", text or "")
    listed = re.findall(r"\b([A-H])\b", others[-1].upper()) if others and others[-1].lower() != "none" else []
    return (answers[-1].strip() if answers else None), listed


def _number(s: str) -> Fraction | None:
    s = re.sub(r"[\s,$%]", "", s or "").replace("−", "-")
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None


def agrees(item: Item, answer: str | None) -> bool:
    if not answer:
        return False
    keys = json.loads(item.key or "[]")
    if item.format == "numeric":
        got = _number(answer)
        return got is not None and any(_number(k) == got for k in keys)
    m = re.match(r"\W*([A-H])\b", answer.strip(), re.I)
    return bool(m) and m.group(1).upper() in {k.strip().upper() for k in keys}


@dataclass
class Solve:
    answer: str | None
    agrees: bool
    others: list[str]
    call_id: str


def solve_once(client, item: Item, section: str, model: str, household: str) -> Solve:
    call_id = new_call(household, "blind_solve", item.id)
    msg = parse_with_receipt(
        client, call_id=call_id, stage="blind_solve", job_id=item.id, model=model,
        max_tokens=MAX_TOKENS[section], system=SYSTEM, messages=build_messages(item, section),
    )
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    answer, others = parse_reply(text)
    return Solve(answer, agrees(item, answer), others, call_id)


@dataclass
class Report:
    candidates: int = 0
    passed: int = 0
    passed_on_retry: int = 0
    disputed: int = 0
    errors: int = 0
    stopped: str | None = None


def pending_ids(db, *, section: str | None, recheck: bool, limit: int | None) -> list[tuple[str, str]]:
    """(item_id, section) for verified official items still lacking a blind_solve check. Hard Math first."""
    q = (select(Item.id, Skill.section).join(Skill, Skill.id == Item.skill_id)
         .where(Item.origin == "official", Item.status == "verified"))
    if section:
        q = q.where(Skill.section == section)
    rows = db.execute(q).all()
    if not recheck:
        done = set(db.scalars(select(ItemCheck.item_id).where(ItemCheck.check == "blind_solve")))
        rows = [r for r in rows if r[0] not in done]
    order = {"hard": 0, "medium": 1, "easy": 2}
    diff = dict(db.execute(select(Item.id, Item.difficulty)).all())
    rows.sort(key=lambda r: (r[1] != "math", order.get(diff.get(r[0]), 3), r[0]))
    return [(i, s) for i, s in rows][: limit or None]


def _check_one(client, item_id: str, section: str, model: str, household: str, report: Report, lock, stop) -> None:
    if stop.is_set():
        return
    with SessionLocal() as db:
        item = db.get(Item, item_id)
        try:
            first = solve_once(client, item, section, model, household)
            second = None
            if not first.agrees:
                second = solve_once(client, item, section, model, household)
            ok = first.agrees or bool(second and second.agrees)
            detail = {"first": first.answer, "second": second.answer if second else None, "others": first.others,
                      "key": json.loads(item.key or "[]")}
            db.query(ItemCheck).filter(ItemCheck.item_id == item.id, ItemCheck.check == "blind_solve").delete()
            db.add(ItemCheck(item_id=item.id, check="blind_solve", passed=ok, model_id=model,
                             receipt_id=(second or first).call_id, detail=json.dumps(detail)))
            if not ok:
                item.status = "review"  # key disputed twice: out of service until a human decides
            db.commit()
            with lock:
                report.passed += ok
                report.passed_on_retry += bool(ok and not first.agrees)
                report.disputed += not ok
        except ProviderBudgetFailure as error:
            db.rollback()
            with lock:
                report.stopped = str(error)
            stop.set()
        except Exception as error:  # one bad item must not stop a long run
            db.rollback()
            logs.record_error(error, job_id=item_id)
            with lock:
                report.errors += 1


def run(client, *, section=None, limit=None, workers=4, model=None, recheck=False, household="family") -> Report:
    model = model or config.MODEL_CHECK_ID or config.MODEL_ID
    with SessionLocal() as db:
        todo = pending_ids(db, section=section, recheck=recheck, limit=limit)
    report = Report(candidates=len(todo))
    lock, stop = threading.Lock(), threading.Event()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for item_id, sec in todo:
            pool.submit(_check_one, client, item_id, sec, model, household, report, lock, stop)
    return report


def estimate(*, section=None, limit=None, recheck=False, model=None, retry_rate=0.10) -> dict:
    """Planning estimate only: output length is assumed, not measured. Prices come from provider_usage rates."""
    model = model or config.MODEL_CHECK_ID or config.MODEL_ID
    rate_in, rate_out = model_rates(model)
    with SessionLocal() as db:
        todo = pending_ids(db, section=section, recheck=recheck, limit=limit)
        tin = tout = images = 0
        for item_id, sec in todo:
            item = db.get(Item, item_id)
            blocks = [b for m in build_messages(item, sec) for b in m["content"]]
            tin += int(sum(len(b["text"]) for b in blocks if b["type"] == "text") / 3.5) + 250  # + system prompt
            n_img = sum(b["type"] == "image" for b in blocks)
            images += n_img
            tin += n_img * 150
            tout += OUTPUT_TOKENS_ASSUMED[sec]
    scale = 1 + retry_rate
    cost = (tin * rate_in + tout * rate_out) * scale / 1_000_000 if rate_in and rate_out else None
    return {"items": len(todo), "model": model, "input_tokens": int(tin * scale), "output_tokens": int(tout * scale),
            "images": images, "assumes_retry_rate": retry_rate,
            "estimated_usd": round(cost, 2) if cost is not None else "unknown rates for this model"}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Blind-solve verification of official answer keys")
    parser.add_argument("--section", choices=["math", "rw"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model")
    parser.add_argument("--recheck", action="store_true", help="re-solve items that already have a blind_solve check")
    parser.add_argument("--estimate", action="store_true", help="print a cost estimate and exit; calls no model")
    args = parser.parse_args(argv)
    logs.setup("keycheck")
    if args.estimate:
        print(json.dumps(estimate(section=args.section, limit=args.limit, recheck=args.recheck, model=args.model), indent=1))
        print(f"Monthly cap is ${config.PEAK_COST_LIMIT_MONTH}. If the estimate is higher, raise it for this run: "
              "PEAK_COST_LIMIT_MONTH=<usd>")
        return
    import anthropic

    client = anthropic.Anthropic(api_key=provider_keys.key_for(), timeout=config.PROVIDER_TIMEOUT_SECONDS)
    report = run(client, section=args.section, limit=args.limit, workers=args.workers, model=args.model,
                 recheck=args.recheck)
    print(json.dumps(report.__dict__, indent=1))
    if report.stopped:
        raise SystemExit(f"STOPPED EARLY: {report.stopped}. Re-run to resume; finished items are skipped.")


if __name__ == "__main__":
    main()
