# Peak on the Mac

Peak v1 runs entirely on Addison's MacBook: one process serves the screens and the data on `127.0.0.1`.
There is no server, no account to manage, and nothing leaves the machine.

## First-time setup (about 10 minutes)

Needs Homebrew, then:

```bash
brew install uv node
```

Get the code somewhere **outside** iCloud-synced folders (`~/Documents` and `~/Desktop` can be synced):

```bash
mkdir -p ~/code && cd ~/code && git clone https://github.com/thematthewturner/peak.git && cd peak
```

Build the screens once (and again after each update):

```bash
cd apps/web && npm ci && npm run build && cd ../..
```

Load the question bank into this Mac's Peak:

```bash
cd services/backend && uv run python -m peak.local import ~/Documents/projects/sat-questions/data/collegeboard_qbank.jsonl
```

Install the app icon (creates `~/Applications/Peak.app`):

```bash
cd ~/code/peak && ./scripts/install-mac-app.sh
```

Open **Peak** from Spotlight or Finder and drag it to the Dock. It opens straight into Today.

## Everyday

- **Open:** click Peak in the Dock. Closing the window quits it.
- **Where the data lives:** `~/Library/Application Support/Peak` (database, backups). Turn on Time Machine.
- **Backups:** Peak copies the database to `backups/` every time it opens and keeps the last 14.
- **Logs:** `~/Library/Logs/Peak.log`.

## Updating

```bash
cd ~/code/peak && git pull && (cd apps/web && npm ci && npm run build)
```

Then reopen Peak. Database changes apply automatically on the next open, and her history is kept.

## Useful commands (from `services/backend`)

```bash
uv run python -m peak.local where     # paths and counts
uv run python -m peak.local backup    # an extra backup right now
uv run python -m peak.local --no-window   # serve only; prints the address to open in a browser
```

## Parent access

Peak opens straight into Addison's account using a one-time token from the launcher. A parent account can be
added for the sign-in page:

```bash
cd services/backend && uv run python -m peak.local add-parent matt
```

## Known v1 limits

- The Dock may show a Python icon while Peak runs; a fully bundled app is the next milestone.
- Timed mode (the Bluebook-style runner) is not in v1. It ships before May 15, 2027.
- The key check (`peak.keycheck`) works but needs an Anthropic key; see `docs/DATA.md`.
