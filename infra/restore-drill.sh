#!/usr/bin/env bash
# Read-only source snapshot; isolated disposable database; no app/provider calls.
set -euo pipefail
umask 077
if [[ $# != 1 ]]; then echo 'Usage: restore-drill.sh SNAPSHOT_DIRECTORY' >&2; exit 2; fi
snapshot=$(cd "$1" && pwd)
format=custom
if [[ -f "$snapshot/database.dump" && -d "$snapshot/files" ]]; then :
elif [[ -f "$snapshot/database.sql.gz" && -f "$snapshot/files.tar.gz" ]]; then format=legacy
else echo 'Missing custom or legacy backup database/files pair' >&2; exit 2; fi
started=$(date +%s)
command -v docker >/dev/null
private_dir=$(mktemp -d "${TMPDIR:-/tmp}/peak-restore.XXXXXX")
container="peak-restore-$(date +%s)-$$"
cleanup() { docker rm -f -v "$container" >/dev/null 2>&1 || true; rm -rf "$private_dir"; }
trap cleanup EXIT
if [[ "$format" == custom ]]; then
  cp -a "$snapshot/files" "$private_dir/files"
else
  # Extract only file artifacts, never peak.env or any production environment.
  python3 - "$snapshot/files.tar.gz" "$private_dir" <<'PY_EXTRACT'
import pathlib, sys, tarfile
archive, destination = sys.argv[1:]
with tarfile.open(archive, "r:gz") as stream:
    for member in stream.getmembers():
        parts = pathlib.PurePosixPath(member.name).parts
        if not parts or parts[0] != "files" or ".." in parts or member.issym() or member.islnk():
            raise SystemExit("Unsafe or unexpected archive entry")
    stream.extractall(destination, filter="data")
if not (pathlib.Path(destination) / "files").is_dir():
    raise SystemExit("Restored files directory missing")
PY_EXTRACT
fi
if [[ -f "$snapshot/files.sha256" ]]; then
  cp "$snapshot/files.sha256" "$private_dir/files.sha256"
  (cd "$private_dir" && sha256sum --check files.sha256)
else
  echo 'Legacy snapshot has no manifest; file hashes cannot be validated against backup-time values.' >&2
fi
# --network none, no host ports, no production mounts, disposable anonymous volume.
docker run -d --name "$container" --network none --memory 512m --tmpfs /tmp \
  -e POSTGRES_USER=restore -e POSTGRES_DB=restore -e POSTGRES_HOST_AUTH_METHOD=trust \
  postgres:17.9-bookworm >/dev/null
for attempt in {1..60}; do
  if docker exec "$container" pg_isready -U restore -d restore >/dev/null 2>&1; then break; fi
  sleep 1
done
# SQL stderr is kept in the private temporary directory, never printed because
# a COPY failure might include student record contents.
if [[ "$format" == custom ]]; then
  if ! docker exec -i "$container" pg_restore --exit-on-error --no-owner --no-privileges -U restore -d restore < "$snapshot/database.dump" > "$private_dir/restore.log" 2>&1; then
    echo 'Isolated database restore failed; no live data changed.' >&2; exit 1
  fi
else
  docker exec "$container" psql -v ON_ERROR_STOP=1 -U restore -d restore -c 'CREATE ROLE peak;' >/dev/null
  if ! gzip -dc "$snapshot/database.sql.gz" | docker exec -i "$container" psql -v ON_ERROR_STOP=1 --single-transaction -U restore -d restore > "$private_dir/restore.log" 2>&1; then
    echo 'Isolated legacy SQL restore failed; no live data changed.' >&2; exit 1
  fi
fi
# Verify schema and count key recovered records without revealing student data.
docker exec "$container" psql -v ON_ERROR_STOP=1 -U restore -d restore -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
docker exec "$container" psql -v ON_ERROR_STOP=1 -U restore -d restore -c \
  "SELECT count(*) AS accounts FROM users; SELECT count(*) AS quizzes FROM corpus_quizzes;"
docker exec "$container" psql -v ON_ERROR_STOP=1 -At -U restore -d restore -c \
  "SELECT COALESCE(json_agg(path), '[]'::json) FROM (SELECT path FROM source_files UNION ALL SELECT path FROM corpus_work UNION ALL SELECT pdf_path AS path FROM study_sessions UNION ALL SELECT path FROM submissions UNION ALL SELECT original_path AS path FROM submissions) AS artifacts WHERE path IS NOT NULL AND path <> '';" > "$private_dir/artifact-paths.json"
python3 - "$private_dir/files" "$private_dir/artifact-paths.json" <<'PY_PATHS'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
paths = json.loads(pathlib.Path(sys.argv[2]).read_text())
missing = outside = 0
for value in paths:
    if not isinstance(value, str) or not value.startswith("/data/"):
        outside += 1
        continue
    relative = pathlib.PurePosixPath(value[6:])
    candidate = (root / str(relative)).resolve()
    if ".." in relative.parts or not candidate.is_relative_to(root):
        outside += 1
    elif not candidate.is_file():
        missing += 1
if missing or outside:
    raise SystemExit(f"Artifact verification failed: missing={missing}, outside_data={outside}")
print(f"Artifact verification passed: {len(paths)} database references exist in restored files.")
PY_PATHS
printf 'Restore drill complete: format=%s completed_at=%s duration_seconds=%s. Temporary database/files removed on exit.\n' "$format" "$(date -u +%FT%TZ)" "$(( $(date +%s) - started ))"
