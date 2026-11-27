#!/usr/bin/env bash
# Deploy a CI-built release of Peak only. Never touches the edge proxy or Belay.
set -euo pipefail
umask 077
if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then echo 'Usage: deploy.sh FULL_COMMIT_SHA' >&2; exit 2; fi
release=$1
cd /opt/peak
compose=(docker compose --env-file /etc/peak/peak.env -f infra/compose.yaml)
# Resolve config only in a pipe; it contains secrets and must never be printed.
"${compose[@]}" config --format json | PYTHONPATH=services/backend python3 -m peak.operational_checks "$release"
if [[ -n "${PEAK_IMAGE_DELIVERY_DIR:-}" ]]; then
  # SSH delivery is still CI-built, never an on-host source build.
  for repository in peak-backend peak-web; do
    delivery="$PEAK_IMAGE_DELIVERY_DIR/image-$repository"
    [[ "$(cat "$delivery/revision.txt")" == "$release" ]] || { echo 'CI archive revision mismatch' >&2; exit 1; }
    [[ "$(cat "$delivery/archive.sha256")" =~ ^[0-9a-f]{64}[[:space:]][[:space:]]image.tar.gz$ ]] || { echo 'Invalid image archive manifest' >&2; exit 1; }
    (cd "$delivery" && sha256sum --check archive.sha256)
    docker load --input "$delivery/image.tar.gz" >/dev/null
  done
  "${compose[@]}" pull postgres
else
  "${compose[@]}" pull
fi
for repository in peak-backend peak-web; do
  image="ghcr.io/thematthewturner/$repository:$release"
  actual=$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image")
  [[ "$actual" == "$release" ]] || { echo "Image revision verification failed: $repository" >&2; exit 1; }
done
# Every upgrade requires a fresh restic backup or a recent verified manual export.
backup_mode=${PEAK_BACKUP_MODE:-$(grep -E '^PEAK_BACKUP_MODE=' /etc/peak/peak.env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)}
backup_mode=${backup_mode:-restic}
if [[ "$backup_mode" == none ]]; then
  echo 'WARNING: PEAK_BACKUP_MODE=none; deploying without a backup. Keep an independent backup (e.g. DigitalOcean Droplet backups).' >&2
elif [[ "$backup_mode" == manual-download ]]; then
  receipt=${PEAK_MANUAL_BACKUP_RECEIPT:-/srv/peak/backups/manual-download-receipt.json}
  PYTHONPATH=services/backend python3 -m peak.operational_checks manual-backup "$receipt"
elif [[ -f /etc/peak/backup.env ]]; then
  /opt/peak/infra/backup.sh
else
  echo 'Deployment stopped: configure restic or verify a manually downloaded encrypted backup.' >&2
  exit 1
fi
running_image() {
  local id
  id=$("${compose[@]}" ps -q "$1" 2>/dev/null | head -n 1 || true)
  if [[ -n "$id" ]]; then docker inspect --format '{{.Config.Image}}' "$id" 2>/dev/null || true; fi
}
previous_backend=$(running_image api)
previous_web=$(running_image web)
# Drain: the worker claims nothing new; running jobs get up to 10 minutes to finish.
if [[ -n "$previous_backend" ]] && "${compose[@]}" exec -T api python -m peak.ops_report drain >/dev/null 2>&1; then
  echo 'Draining: waiting up to 10 minutes for running jobs to finish.'
  deadline=$((SECONDS + 600))
  while :; do
    running=$("${compose[@]}" exec -T api python -m peak.ops_report running 2>/dev/null | tail -n 1 || true)
    [[ "$running" =~ ^[0-9]+$ ]] || { echo 'WARNING: could not count running jobs; continuing.' >&2; break; }
    if (( running == 0 )); then echo 'Drained: no jobs running.'; break; fi
    if (( SECONDS >= deadline )); then echo "WARNING: drain timed out; $running running job(s) will be cut off." >&2; break; fi
    sleep 5
  done
else
  echo 'Drain unavailable; continuing.' >&2
fi
"${compose[@]}" stop api worker web
"${compose[@]}" up -d --wait --wait-timeout 60 postgres
db_revision() { "${compose[@]}" run --rm --no-deps api alembic current 2>/dev/null | awk 'NF {print $1}' | sort | tr '\n' ' '; }
revision_before=$(db_revision)
"${compose[@]}" run --rm --no-deps api alembic upgrade head
revision_after=$(db_revision)
"${compose[@]}" up -d --remove-orphans
wait_ready() {
  local attempt
  for attempt in {1..30}; do
    if "${compose[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/readiness',timeout=5)" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}
if ! wait_ready; then
  if [[ "$revision_before" != "$revision_after" ]]; then
    echo 'Release readiness failed AFTER a database migration was applied. NOT rolling back; inspect service logs and restore from backup if needed.' >&2
  elif [[ -n "$previous_backend" && -n "$previous_web" ]]; then
    echo 'Release readiness failed and no migration was applied. Restoring the previous images.' >&2
    BACKEND_IMAGE=$previous_backend WEB_IMAGE=$previous_web "${compose[@]}" up -d --remove-orphans
    if wait_ready; then echo "Rolled back to $previous_backend and $previous_web." >&2; else echo 'Rollback did not become ready either. Inspect service logs.' >&2; fi
  else
    echo 'Release readiness failed and no previous images were recorded. Inspect service logs.' >&2
  fi
  exit 1
fi
printf 'Release %s is ready.\n' "$release"
