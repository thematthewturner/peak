#!/usr/bin/env bash
# Consistent manually downloaded backup. Recipient private key stays on the Mac.
set -euo pipefail
umask 077
if [[ $# != 1 || ! -f "$1" ]]; then echo 'Usage: export-backup.sh RECIPIENT_PUBLIC_CERTIFICATE' >&2; exit 2; fi
recipient=$(realpath "$1")
openssl x509 -in "$recipient" -noout >/dev/null
cd /opt/peak
compose=(docker compose --env-file /etc/peak/peak.env -f infra/compose.yaml)
output_dir=/srv/peak/backups/manual
mkdir -p "$output_dir"
chmod 700 "$output_dir"
staging_dir=$(mktemp -d /srv/peak/backup-export.XXXXXX)
stopped=0
output=$(mktemp "$output_dir/peak-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX.cms")
complete=0
cleanup() {
  result=$?
  trap - EXIT
  if (( stopped )); then if ! "${compose[@]}" start api worker; then result=1; fi; fi
  rm -rf "$staging_dir"
  if (( ! complete )); then rm -f "$output" "$output.sha256"; fi
  exit "$result"
}
trap cleanup EXIT
stopped=1
"${compose[@]}" stop api worker
"${compose[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$staging_dir/database.dump"
cp -a /srv/peak/data/files "$staging_dir/files"
cp /etc/peak/peak.env "$staging_dir/peak.env"
(cd "$staging_dir" && find files -type f -print0 | sort -z | xargs -0 -r sha256sum > files.sha256 && sha256sum database.dump peak.env files.sha256 > bundle.sha256)
"${compose[@]}" start api worker
stopped=0
# AES-GCM authenticates the encrypted CMS envelope. Only the public recipient
# certificate reaches this host; no decryption secret is needed or retained here.
tar -C "$staging_dir" -czf - database.dump files files.sha256 bundle.sha256 peak.env | \
  openssl cms -encrypt -binary -aes-256-gcm -outform DER -out "$output" "$recipient"
sha256sum "$output" > "$output.sha256"
complete=1
printf 'Encrypted export ready: %s\n' "$output"
echo 'Download ciphertext and checksum, authenticate/decrypt locally, verify its manifest, then write the verified download receipt. Keep the private key separately.'
