# Private corpus: rules (PRD s8.5)

- The repo contains **zero** official content. `corpus-data/`, `*.pdf` and `*.jsonl` exports are git-ignored.
- Content enters only as files the owner downloaded or scanned. The importers (`peak.qbank`, `peak.corpus.ingest`)
  fingerprint by SHA-256, so re-uploading is a no-op, and store under `DATA_DIR/sources` (mode 0600, never served).
- Auth-gated, no public URLs, no sharing, purgeable by source.
- Benchmark forms (`benchmark_locked`) are never served in drills or `/api/items/next`.
- Question Bank exports were collected with local crawlers. PRD s8.5 specifies manual downloads only, no scraping;
  the owner should check College Board's terms for that collection method.

## Importing the Question Bank

```bash
cd services/backend
python -m peak.seed                                   # skill tree (idempotent)
python -m peak.qbank /path/to/collegeboard_qbank.jsonl   # prints created / duplicates / rejected / unmatched skills
python -m peak.qbank /path/to/test_items.jsonl --kind practice_test --benchmark-locked
```

The importer is tolerant of field names (see `peak/qbank.py`). Items import as `verified` only if schema and
the official key pass; the blind-solve and SymPy checks run later as worker jobs and may pull an item.
