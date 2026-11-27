import pymupdf as fitz
import pytest

from peak.corpus import ingest


def make_pdf(pages):
    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    return pdf.tobytes()


QB = [
    "Question ID 1a2b3c4d\nWhat is 2+2?\nA. 3\nB. 4",
    "C. 5\nD. 6\nQuestion ID 99ffee00\nSolve x = 3.",
]


def test_upload_stores_privately_and_dedupes(db):
    data = make_pdf(QB)
    doc, created = ingest.store_upload(db, data, "qbank_export")
    again, created2 = ingest.store_upload(db, data, "qbank_export")
    assert created and not created2 and doc.id == again.id and doc.pages == 2
    path = __import__("pathlib").Path(doc.path)
    assert path.exists() and oct(path.stat().st_mode & 0o777) == "0o600"


def test_rejects_non_pdf_and_bad_kind(db):
    with pytest.raises(ingest.IngestError):
        ingest.store_upload(db, b"not a pdf", "qbank_export")
    with pytest.raises(ingest.IngestError):
        ingest.store_upload(db, make_pdf(["x"]), "mystery")


def test_segment_qbank_spans_pages():
    segs = ingest.segment_qbank(QB)
    assert [s.ref for s in segs] == ["1a2b3c4d", "99ffee00"]
    assert segs[0].pages == (0, 1) and "C. 5" in segs[0].text and "Solve" not in segs[0].text
    assert segs[1].pages == (1,)


def test_segment_practice_test():
    segs = ingest.segment_practice_test(["Question 1\nfoo\nQuestion 2\nbar", "Question 3\nbaz"])
    assert [s.ref for s in segs] == ["S1M1Q1", "S1M1Q2", "S1M1Q3"]


def test_verify_extraction_catches_hallucinated_text():
    src = "Question ID abc What is 2+2? A. 3 B. 4 C. 5 D. 6"
    good = {"stem": "What is 2+2?", "choices": {"A": "3", "B": "4", "C": "5", "D": "6"}, "key": ["B"], "format": "mc"}
    assert all(p for _, p, _ in ingest.verify_extraction(good, src, had_figure=False))
    bad = {**good, "stem": "What is 3+3 apples?"}
    assert not dict((n, p) for n, p, _ in ingest.verify_extraction(bad, src, had_figure=False))["text_match"]
    nokey = {**good, "key": []}
    assert not dict((n, p) for n, p, _ in ingest.verify_extraction(nokey, src, had_figure=False))["key_present"]
    assert not dict((n, p) for n, p, _ in ingest.verify_extraction(good, src, had_figure=True))["figure"]


def test_extract_segment_passes_page_images_to_injected_extractor(db):
    doc, _ = ingest.store_upload(db, make_pdf(QB), "qbank_export")
    seg = ingest.segment_qbank(ingest.page_texts(doc.path))[0]
    seen = {}

    def fake(segment, images):
        seen["n"] = len(images)
        return {"stem": "x", "key": ["A"], "format": "numeric"}

    out = ingest.extract_segment(seg, doc.path, fake)
    assert seen["n"] == 2 and out["key"] == ["A"]


def test_upload_route_parent_only(clients):
    parent, student = clients
    data = make_pdf(QB)
    files = {"file": ("x.pdf", data, "application/pdf")}
    assert student.post("/api/admin/corpus/upload", data={"kind": "qbank_export"}, files=files).status_code == 403
    r = parent.post("/api/admin/corpus/upload", data={"kind": "qbank_export"}, files=files)
    assert r.status_code == 200 and r.json()["created"] is True
    again = parent.post("/api/admin/corpus/upload", data={"kind": "qbank_export"}, files={"file": ("y.pdf", data, "application/pdf")})
    assert again.json()["created"] is False
    assert student.get("/api/admin/corpus/documents").status_code == 403
    assert len(parent.get("/api/admin/corpus/documents").json()) == 1
