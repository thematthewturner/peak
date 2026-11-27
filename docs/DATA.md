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

## Verifying the official answer keys (blind solve)

The importer trusts the official key. `peak.keycheck` double-checks it: a model solves each item **without** the
key or rationale; on disagreement it solves once more, and only two disagreements pull the item (status
`review`, a failed `blind_solve` check). The official key is never changed automatically. It costs money, so
price it first:

```bash
cd services/backend
uv run python -m peak.keycheck --estimate               # prices the run; calls no model
export ANTHROPIC_API_KEY=...                            # Peak's own key (see .env.example)
PEAK_COST_LIMIT_MONTH=150 uv run python -m peak.keycheck --section math --limit 50   # small trial first
PEAK_COST_LIMIT_MONTH=150 uv run python -m peak.keycheck --section math             # then the rest
```

It resumes where it stopped (finished items are skipped), works Hard Math first, and `--reprocess` imports never
overwrite its results. Review disputed items with:

```bash
sqlite3 .data/peak.db "select i.source_ref, c.detail from items i join item_checks c on c.item_id=i.id where c.check='blind_solve' and not c.passed;"
```
