# Launch runbook: peak.mturner.work

Peak is a separate Compose project. For the first launch it is routed through **Belay's existing Caddy** with a
six-line Compose change and one Caddy block (`docs/launch/belay-route-peak.patch`). The PRD's cleaner "separate
edge proxy" project can come later without changing Peak. Nothing here runs automatically; every step is yours.

Peak makes **no model calls at runtime**, so it needs no Anthropic key to go live. A key is only needed for
`peak.keycheck` and later ingestion.

## 0. Before you touch anything
- [ ] DigitalOcean: **snapshot the Droplet** (this is your rollback for everything below).
- [ ] Resize to 2 vCPU / 4 GB if it is smaller (a short power-off). Add 2 GB swap.
- [ ] Cloudflare: `peak` A record to the Droplet IP, DNS-only (grey cloud) for the first certificate.

## 1. Host preparation (SSH to the Droplet)
```bash
sudo docker network create --subnet 172.31.0.0/24 edge
sudo mkdir -p /srv/peak/data/postgres /srv/peak/data/files /opt/peak /etc/peak
sudo git clone https://github.com/thematthewturner/peak.git /opt/peak
```
Create `/etc/peak/peak.env` from `/opt/peak/.env.example` and `chmod 600` it. Set `POSTGRES_PASSWORD` (and the same
value inside `DATABASE_URL`, URL-encoded), keep `EDGE_PROXY_IP=172.31.0.10`, and leave `PEAK_DEMO=0`. Set
`PEAK_BACKUP_MODE=none` for the **first deploy only** (there is no data to protect yet).

## 2. Route the hostname (this touches Belay: do it off-hours)
Apply `docs/launch/belay-route-peak.patch` to the Belay repo (as a PR to Belay, or by hand in `/opt/belay`). It
adds the `peak.mturner.work` site block and attaches Belay's proxy to the `edge` network. Deploy Belay as usual
(`deploy.sh` validates the Caddyfile first). Expect Belay's proxy to restart: roughly 10-30 seconds of downtime.
Check Belay is healthy before continuing.

## 3. Ship the code
1. Merge the Peak PR(s) to `main`. `Verify Peak` runs; on `main` it publishes `peak-backend` and `peak-web` images
   tagged with the commit SHA to GHCR.
2. On the Droplet: `docker login ghcr.io` with a token that has `read:packages`.
3. First deploy, by hand:
```bash
cd /opt/peak && git fetch origin && git checkout --detach <FULL_40_CHAR_SHA>
sudo sed -i -E "s#^WEB_IMAGE=.*#WEB_IMAGE=ghcr.io/thematthewturner/peak-web:<SHA>#; s#^BACKEND_IMAGE=.*#BACKEND_IMAGE=ghcr.io/thematthewturner/peak-backend:<SHA>#" /etc/peak/peak.env
sudo /opt/peak/infra/deploy.sh <FULL_40_CHAR_SHA>
```
`deploy.sh` checks the image labels, runs the migration, and waits for `/api/readiness`.

## 4. First-run setup
```bash
cd /opt/peak && C="docker compose --env-file /etc/peak/peak.env -f infra/compose.yaml"
sudo $C run --rm peak-api python -m peak.manage addison --role student
sudo $C run --rm peak-api python -m peak.manage matt --role parent
sudo $C run --rm peak-api python -m peak.seed
```
Copy the question export to the host (`scp collegeboard_qbank.jsonl you@droplet:/srv/peak/data/files/`), then:
```bash
sudo $C run --rm peak-api python -m peak.qbank /data/collegeboard_qbank.jsonl
```
Expect about 4,105 `verified`. Optionally run the key check (see `docs/DATA.md`; needs the Anthropic key).

## 5. Verify it is really live
- [ ] `curl -fsSI https://peak.mturner.work/api/health` returns 200 with an `x-request-id` header
- [ ] `https://peak.mturner.work/api/readiness` returns `"status":"ok"` (the worker heartbeat is fresh)
- [ ] Sign in as Addison on her phone; Practice serves a question; a graph question renders
- [ ] A miss shows the cold-retry step and hides the solution until she retries
- [ ] Belay still works (log in, open a quiz)
- [ ] `docker stats --no-stream`: no container near its memory limit

## 6. Make it durable
1. Set `PEAK_BACKUP_MODE=restic`, create `/etc/peak/backup.env` (separate Spaces prefix), install
   `infra/peak-backup.{service,timer}` (04:00, an hour after Belay's), run `infra/backup.sh` once and
   `infra/restore-drill.sh` against that snapshot. **Do not skip the restore drill.**
2. Deploy automation: repo secrets `PEAK_OPS_SSH_KEY`, `PEAK_OPS_KNOWN_HOSTS`, `PEAK_OPS_HOST`, `PEAK_OPS_USER`;
   a `production` environment with you as required reviewer; install `infra/ops-entry.sh` as the forced command.
3. Flip Cloudflare to proxied (orange cloud) with SSL mode **Full (strict)** once the certificate is issued.

## Rollback
- **Peak misbehaves:** `docker compose -p peak down` (Belay is unaffected), or just remove the `peak.mturner.work`
  block from Belay's Caddyfile and reload.
- **Belay misbehaves after step 2:** revert the Belay commit and redeploy; if the proxy will not start, restore the
  Droplet snapshot.

## Known risks
- Step 2 restarts Belay's proxy (brief Belay outage) and is the only step that touches the existing site.
- A shared 4 GB host: ingestion and key checks should run off-hours, and an alert on memory is worth adding.
- Let's Encrypt rate limits: leave Cloudflare DNS-only until the first certificate is issued.
- No CI run has exercised `deploy.sh`, the backup scripts or the Docker builds on a real host. Expect to fix a
  small thing or two on the first pass, and do it with the snapshot in hand.
