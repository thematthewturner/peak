#!/usr/bin/env bash
# Forced-command entry point for the CI ops SSH key. The key can run ONLY the allowlisted
# verbs below; it never gets a shell, port forwarding or a PTY.
#
# Install a root-owned COPY outside the checkout so a pushed commit cannot change what the key runs:
#   sudo install -o root -g root -m 755 /opt/peak/infra/ops-entry.sh /usr/local/bin/peak-ops
# Then add ONE line to the deploy user's ~/.ssh/authorized_keys:
#   command="/usr/local/bin/peak-ops",restrict ssh-ed25519 AAAA... peak-ci-ops
#
# Verbs (passed by ssh as SSH_ORIGINAL_COMMAND):
#   status                 release SHA, images, non-secret model config, health, backup age
#   diagnose [HOURS]       recent job failures, timings and token usage (no item text, no answers)
#   deploy FULL_SHA        checkout SHA, point images at it, run infra/deploy.sh
set -euo pipefail
umask 077

readonly ROOT=/opt/peak
readonly ENV_FILE=/etc/peak/peak.env
readonly REGISTRY=ghcr.io/thematthewturner

compose() { docker compose --env-file "$ENV_FILE" -f "$ROOT/infra/compose.yaml" "$@"; }

sql() {
  compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -q -P pager=off -v ON_ERROR_STOP=1' <<<"$1"
}

section() { printf '\n== %s ==\n' "$1"; }

status() {
  section "release"
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo "checkout: not a git repository"
  grep -E '^(WEB_IMAGE|BACKEND_IMAGE|PEAK_ENV|MODEL_ID|MODEL_CHECK_ID|PROVIDER_TIMEOUT_SECONDS|PEAK_[A-Z_]+LIMIT[A-Z_]*|INGEST_[A-Z_]+|LOG_[A-Z_]+|MODEL_[A-Z_]*USD_PER_MILLION|MAX_UPLOAD_BYTES|PEAK_BACKUP_MODE|[A-Z]+_MEMORY_LIMIT)=' "$ENV_FILE" || true
  for key in ANTHROPIC_API_KEY; do
    if grep -qE "^${key}(_FILE)?=.+" "$ENV_FILE"; then echo "$key: set"; else echo "$key: unset"; fi
  done
  section "containers"
  compose ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'
  # shellcheck disable=SC2046
  docker inspect --format '{{.Name}} restarts={{.RestartCount}} oom_killed={{.State.OOMKilled}}' $(compose ps -q) || true
  section "readiness"
  compose exec -T peak-api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/readiness', timeout=5).read().decode())" || echo "readiness: unavailable"
  section "host"
  df -h /srv/peak | tail -1
  free -m | sed -n 2p
  docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' || true
  section "backup"
  cat /srv/peak/backup-status 2>/dev/null || echo "restic status: none"
  receipt=/srv/peak/backups/manual-download-receipt.json
  if [[ -r "$receipt" ]]; then
    python3 -c "import json,sys,time; r=json.load(open(sys.argv[1])); print('manual receipt age_hours=%.1f' % ((time.time()-r['verified_at'])/3600))" "$receipt"
  else
    echo "manual receipt: none"
  fi
}

diagnose() {
  local hours=${1:-48}
  [[ "$hours" =~ ^[0-9]{1,3}$ ]] || { echo "HOURS must be 1-999" >&2; exit 2; }
  section "worker/api warnings (last ${hours}h)"
  compose logs --since "${hours}h" --no-color worker peak-api 2>&1 \
    | grep -E 'Job failed|Lease heartbeat|Traceback|Error|Exception|Killed|OOM' | tail -n 200 || true
  section "recent jobs"
  sql "select created, kind, state, model_id, left(coalesce(error,''), 160) as error
       from jobs order by created desc limit 25;"
  section "job stage durations, last 30 days (ms)"
  sql "select stage, count(*) as n,
              percentile_cont(0.5) within group (order by (detail::json->>'ms')::numeric) as p50_ms,
              percentile_cont(0.95) within group (order by (detail::json->>'ms')::numeric) as p95_ms
       from job_events
       where detail::jsonb ? 'ms' and created > to_char(now() at time zone 'utc' - interval '30 days', 'YYYY-MM-DD')
       group by stage order by stage;"
  section "ingestion by status"
  sql "select kind, status, count(*) as files, sum(pages) as pages from source_documents group by kind, status order by kind, status;"
  section "unexpected errors (class and code frames only)"
  sql "select created, service, coalesce(route, job_id) as at, request_id, error_class, left(frames, 300) as frames
       from error_events order by created desc limit 20;"
  section "provider calls this month"
  sql "select kind, state, count(*) as calls, sum(input_tokens) as input_tokens,
              sum(output_tokens) as output_tokens, round(sum(cost_usd)::numeric, 2) as usd
       from provider_calls where created like to_char(now() at time zone 'utc', 'YYYY-MM') || '%'
       group by kind, state order by kind, state;"
}

deploy() {
  local sha=${1:-}
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "Usage: deploy FULL_40_CHARACTER_SHA" >&2; exit 2; }
  local previous
  previous=$(git -C "$ROOT" rev-parse HEAD)
  echo "previous release: $previous"
  git -C "$ROOT" fetch --quiet origin
  git -C "$ROOT" checkout --quiet --detach "$sha"
  cp -p "$ENV_FILE" "$ENV_FILE.previous"
  sed -i -E \
    -e "s#^WEB_IMAGE=.*#WEB_IMAGE=${REGISTRY}/peak-web:${sha}#" \
    -e "s#^BACKEND_IMAGE=.*#BACKEND_IMAGE=${REGISTRY}/peak-backend:${sha}#" \
    "$ENV_FILE"
  # deploy.sh enforces image labels, the backup gate, quiesced migrations and readiness.
  # Roll back with: deploy $previous
  "$ROOT/infra/deploy.sh" "$sha"
}

main() {
  local -a argv
  read -r -a argv <<<"${SSH_ORIGINAL_COMMAND:-}"
  case "${argv[0]:-}" in
    status) status ;;
    diagnose) diagnose "${argv[1]:-}" ;;
    deploy) deploy "${argv[1]:-}" ;;
    *) echo "Allowed: status | diagnose [HOURS] | deploy FULL_SHA" >&2; exit 2 ;;
  esac
}

main
