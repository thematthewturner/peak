# Deployment

Peak is its own Compose project (`peak`) on the shared Droplet. It shares only the host and an
external Docker network named `edge`. **Nothing in this repo changes the Droplet by itself.**

## What the owner does (Phase 0, by hand)

1. Snapshot the Droplet, confirm its size, resize to 2 vCPU / 4 GB (PRD D11).
2. Cloudflare: `peak` A record to the Droplet IP.
3. `docker network create edge` and move Belay's Caddy into a small `/opt/edge` project joined to it
   (the one Belay PR, PRD P0). Add a route for Peak:

   ```caddyfile
   peak.mturner.work {
       encode zstd gzip
       header {
           Strict-Transport-Security "max-age=31536000"
           X-Content-Type-Options "nosniff"
           Referrer-Policy "same-origin"
           X-Frame-Options "DENY"
       }
       request_body { max_size 40MB }
       handle /api/* { reverse_proxy api:8000 }
       handle { reverse_proxy web:3000 }
   }
   ```

   Peak's `web` and `api` containers join `edge`; the worker and Postgres never do.
4. `/etc/peak/peak.env` (chmod 600) from `.env.example`. Set `EDGE_PROXY_IP` to the proxy's address on
   `edge`: only it may assert client identity. Use Peak's **own** Anthropic key.
5. Data directories: `/srv/peak/data/{postgres,files}`; release checkout in `/opt/peak`.
6. Backups: `/etc/peak/backup.env` (separate Spaces prefix), then enable `infra/peak-backup.timer`
   (04:00, an hour after Belay's). Run `infra/restore-drill.sh` once.
7. Install the forced-command key: see the header of `infra/ops-entry.sh`. Add repo secrets
   `PEAK_OPS_SSH_KEY`, `PEAK_OPS_KNOWN_HOSTS`, `PEAK_OPS_HOST`, `PEAK_OPS_USER`.

## Release flow

`Verify Peak` (tests, lint, `alembic check`, web build) -> images tagged by commit SHA on GHCR ->
`Deploy production` runs `infra/deploy.sh <sha>` via the forced-command key: label check, backup gate,
drain the worker, migrate while quiesced, readiness check, automatic rollback only if no migration ran.

Create the first accounts on the host: `docker compose ... run --rm api python -m peak.manage addison --role student`
and `... matt --role parent`, then `python -m peak.seed`.
