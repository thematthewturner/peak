# Status

Branch `claude/stoic-wright-1rqvuu`. Backend: 114 tests; web: typecheck, lint, 3 unit tests, production build,
and a Playwright run of the full learner flow.

| WP | Scope | State |
| --- | --- | --- |
| P0 | Belay PR: edge proxy split | Owner action. Not started. See `docs/DEPLOYMENT.md`. |
| P1 | Bootstrap from Belay | Done in repo: auth, budget (`parse_with_receipt`), logging, worker lease/drain, photo normalizer, upload admission, compose project, deploy/backup/ops scripts, CI. Not deployed. |
| P2 | Exam, taxonomy, schema | Done: 29 official skills (87 cells) plus 12 seeded micro-skills, 26 tables, additive migration. CLI accounts via `peak.manage`. |
| P3 | Upload, fingerprint, render, segment | Done (`peak.corpus.ingest`, parent-only upload route). |
| P4 | Extraction and verification | Partial: verification checks and injected extractor are done. **Model extractor job + review UI not built.** Question Bank JSONL import is done (`peak.qbank`) but untested against real data. |
| P5 | Item store, student-safe render, player, entry validator | Done (server and web). |
| P6 | Attempts, benchmarks, form ledger | Done except screenshot intake. |
| P7 | Review, diagnosis, ticket ladder | Done: cold-retry gate, deterministic cause proposal, ladder state machine with persistence. |
| P8 | Priority, composer, Today, school throttle | Done. |
| P9 | FSRS rule cards | Done (API + phone-friendly page). 30 cards seeded. |
| P10 | Progress, weekly digest, export | Progress page only. Digest and export not built. |
| P11 | Scratch-work pipeline | Not started (needs Belay's read/confirm/feedback jobs ported). |
| P12+ | Templates, timed runner, generated R&W, tutor PDF | Not started. **Timed runner (P14) must ship by May 15, 2027.** |

## Known gaps
- Never run against the real Question Bank export (it lives on the owner's machine).
- Postgres path is only exercised in CI (`alembic check` + the suite); local runs use SQLite.
- No admin review UI for items in `review` status.
- No Playwright specs committed; the browser run was done ad hoc.
