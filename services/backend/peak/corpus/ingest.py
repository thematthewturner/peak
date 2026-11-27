"""Official-content ingestion (PRD s8.3): fingerprint, store privately, render, segment, extract, verify.

Files are stored under DATA_DIR/sources by content hash, never in Git, and never served publicly.
Model calls are injected (`extractor`) so the pipeline is testable and always routed through the
budgeted `parse_with_receipt` in production.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from .. import config
from ..models import SourceDocument

SOURCE_DIR = config.DATA_DIR / "sources"
MAX_PAGES = 600
QID = re.compile(r"Question ID\s*:?\s*([0-9a-fA-F]{6,12})")
QNUM = re.compile(r"^\s*Question\s+(\d{1,2})\b", re.M)


class IngestError(ValueError):
    pass


def store_upload(db, data: bytes, kind: str, *, export_filter: dict | None = None) -> tuple[SourceDocument, bool]:
    """Return (document, created). Re-uploading identical bytes is a no-op."""
    if kind not in ("qbank_export", "practice_test", "bluebook_screens", "book_scan"):
        raise IngestError("Unknown source kind")
    if not data.startswith(b"%PDF-"):
        raise IngestError("Only PDF files can be ingested here")
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(SourceDocument).where(SourceDocument.sha256 == digest))
    if existing:
        return existing, False
    SOURCE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = SOURCE_DIR / f"{digest}.pdf"
    path.write_bytes(data)
    path.chmod(0o600)
    pages = page_count(path)
    if pages > MAX_PAGES:
        path.unlink()
        raise IngestError(f"PDF has {pages} pages; the limit is {MAX_PAGES}")
    doc = SourceDocument(sha256=digest, kind=kind, path=str(path), pages=pages, status="uploaded",
                         rights="private_official", export_filter_json=json.dumps(export_filter or {}))
    db.add(doc)
    db.commit()
    return doc, True


def page_count(path: Path) -> int:
    import pymupdf as fitz  # PyMuPDF

    try:
        with fitz.open(path) as pdf:
            return pdf.page_count
    except Exception:
        raise IngestError("This PDF could not be opened") from None


def page_texts(path: str | Path) -> list[str]:
    import pymupdf as fitz

    with fitz.open(path) as pdf:
        return [page.get_text() for page in pdf]


def render_page(path: str | Path, index: int, dpi: int = 110) -> bytes:
    import pymupdf as fitz

    with fitz.open(path) as pdf:
        return pdf[index].get_pixmap(dpi=dpi).tobytes("png")


@dataclass(frozen=True)
class Segment:
    ref: str          # Question ID for exports, "S{section}M{module}Q{n}" for tests
    pages: tuple[int, ...]
    text: str


def segment_qbank(texts: list[str]) -> list[Segment]:
    """Split on Question ID anchors; a question may span pages until the next anchor."""
    segs: list[Segment] = []
    cur_ref, cur_pages, cur_text = None, [], []
    for i, t in enumerate(texts):
        anchors = list(QID.finditer(t))
        if not anchors:
            if cur_ref:
                cur_pages.append(i)
                cur_text.append(t)
            continue
        pos = 0
        for m in anchors:
            if cur_ref:
                chunk = t[pos:m.start()]
                cur_text.append(chunk)
                if chunk.strip() and i not in cur_pages:
                    cur_pages.append(i)  # the question continued onto this page before the next anchor
                segs.append(Segment(cur_ref, tuple(sorted(set(cur_pages))), "\n".join(cur_text)))
            cur_ref, cur_pages, cur_text, pos = m.group(1).lower(), [i], [], m.start()
        cur_text.append(t[pos:])
    if cur_ref:
        segs.append(Segment(cur_ref, tuple(sorted(set(cur_pages))), "\n".join(cur_text)))
    return segs


def segment_practice_test(texts: list[str], section: str = "S1", module: str = "M1") -> list[Segment]:
    segs: list[Segment] = []
    for i, t in enumerate(texts):
        ms = list(QNUM.finditer(t))
        for j, m in enumerate(ms):
            end = ms[j + 1].start() if j + 1 < len(ms) else len(t)
            segs.append(Segment(f"{section}{module}Q{m.group(1)}", (i,), t[m.start():end]))
    return segs


# ---- extraction + verification ---------------------------------------------------------------
REQUIRED = ("stem", "key", "format")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip().lower()


def text_match_ratio(extracted: dict, source_text: str) -> float:
    pieces = [extracted.get("passage"), extracted.get("stem")] + list((extracted.get("choices") or {}).values())
    joined = _norm(" ".join(p for p in pieces if p))
    return _coverage(joined, _norm(source_text)) if joined else 0.0


def _coverage(needle: str, hay: str) -> float:
    """Fraction of needle words found in order within hay (cheap re-render fidelity check)."""
    words = needle.split()
    if not words:
        return 0.0
    hay_words = hay.split()
    i = hits = 0
    for w in words:
        try:
            i = hay_words.index(w, i) + 1
            hits += 1
        except ValueError:
            continue
    return hits / len(words)


def verify_extraction(extracted: dict, source_text: str, *, had_figure: bool, text_threshold: float = 0.99) -> list[tuple[str, bool, str]]:
    checks = []
    missing = [k for k in REQUIRED if not extracted.get(k)]
    checks.append(("schema", not missing, f"missing={missing}"))
    keys = extracted.get("key") or []
    choices = extracted.get("choices") or {}
    ok_key = bool(keys) and (extracted.get("format") == "numeric" or all(str(k).upper() in choices for k in keys))
    checks.append(("key_present", ok_key, "official key present and consistent"))
    ratio = text_match_ratio(extracted, source_text)
    checks.append(("text_match", ratio >= text_threshold, f"ratio={ratio:.3f}"))
    figures = extracted.get("figures") or []
    checks.append(("figure", (not had_figure) or bool(figures), f"had_figure={had_figure} figures={len(figures)}"))
    return checks


Extractor = Callable[[Segment, list[bytes]], dict]


def extract_segment(seg: Segment, path: str | Path, extractor: Extractor) -> dict:
    images = [render_page(path, p) for p in seg.pages]
    return extractor(seg, images)
