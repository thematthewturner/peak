#!/usr/bin/env bash
set -euo pipefail
umask 077
status_file=${PEAK_BACKUP_STATUS_FILE:-/srv/peak/backup-status}
state_dir=$(dirname "$status_file")
mkdir -p "$state_dir"
staging_dir=''
stopped=0
compose=()
finish() {
  result=$?
  trap - EXIT
  if (( stopped )); then
    if ! "${compose[@]}" start peak-api worker; then result=1; fi
  fi
  if [[ -n "$staging_dir" ]]; then rm -rf "$staging_dir"; fi
  marker=$(mktemp "$state_dir/.backup-status.XXXXXX")
  printf 'status=%s\nfinished_at=%s\nexit_code=%s\n' "$([[ $result == 0 ]] && echo success || echo failed)" "$(date -u +%FT%TZ)" "$result" > "$marker"
  mv "$marker" "$status_file"
  exit "$result"
}
trap finish EXIT
# Root-only credentials; failure status contains no credentials or student text.
source /etc/peak/backup.env
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
staging_dir=$(mktemp -d /srv/peak/backup-staging.XXXXXX)
cd /opt/peak
compose=(docker compose --env-file /etc/peak/peak.env -f infra/compose.yaml)
# Suspend writes so database/files share one recovery boundary.
stopped=1
"${compose[@]}" stop peak-api worker
"${compose[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$staging_dir/database.dump"
cp -a /srv/peak/data/files "$staging_dir/files"
(cd "$staging_dir" && find files -type f -print0 | sort -z | xargs -0 -r sha256sum > files.sha256)
"${compose[@]}" start peak-api worker
stopped=0
restic backup --tag peak "$staging_dir"
restic forget --tag peak --group-by tags --keep-daily 7 --keep-weekly 4 --prune
restic check
