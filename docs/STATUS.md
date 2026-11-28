# Status

**v1 is a local Mac app** (see `docs/MAC.md`). One process on 127.0.0.1 serves the screens (a static export) and
the data (SQLite in `~/Library/Application Support/Peak`). The hosted path in `docs/LAUNCH.md` is dormant.

## v1 (built)
- Today: countdown, 5/15/25/40-minute plans with a reason per block, Return to start
- Practice: keyboard-first loop (A-D, S/U/G, Return), cold retry before any answer is shown, friendly diagnosis,
  cause and pattern in two taps ("careless" is not an option), fix saved straight to "retry tomorrow"
- Fixes: five-rung ladder per fix with its cue and next check
- Cards: Space to flip, arrows for knew or missed; FSRS schedule from behavior
- Progress: clean Bluebook trend against the 1400 line and June 5, log scores, non-clean results kept apart
- Launcher: `python -m peak.local` (native window via pywebview, else browser), one-time entry token, loopback-only
  host guard, automatic backup on every open, `import`, `where`, `backup`, `add-parent`
- `scripts/install-mac-app.sh` creates `~/Applications/Peak.app`
- Verified: 166 backend tests; web typecheck, lint, unit tests and export build; a browser run of the full loop

## Next
- Fully bundled Peak.app (own Dock icon), menu bar extra, `⌘K`
- Timed mode (Bluebook runner, Desmos, module trainers) by May 15, 2027
- Run the key check on the real bank; parent digest; scratch-work photos

Earlier hosted-launch notes are kept in git history and `docs/LAUNCH.md`.
