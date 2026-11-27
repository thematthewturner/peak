"""Offline release checks; never print resolved compose secrets."""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

MANUAL_BACKUP_DIR = Path("/srv/peak/backups/manual")


def validate_release(config, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Release requires a full lowercase 40-character commit SHA")
    for service, repository in (("api", "peak-backend"), ("worker", "peak-backend"), ("web", "peak-web")):
        expected = f"ghcr.io/thematthewturner/{repository}:{revision}"
        if config["services"][service]["image"] != expected:
            raise ValueError(f"{service} must use the requested GHCR commit image")
    for service in ("api", "worker", "web", "postgres"):
        if config["services"][service].get("ports"):
            raise ValueError(f"{service} must not expose a host port; the edge proxy owns 80/443")
    if not config["services"]["api"].get("environment", {}).get("FORWARDED_ALLOW_IPS"):
        raise ValueError("FORWARDED_ALLOW_IPS must name the edge proxy address")
    for service in ("worker", "postgres"):
        if "edge" in (config["services"][service].get("networks") or {}):
            raise ValueError(f"{service} must stay off the shared edge network")
    if config.get("name") != "peak":
        raise ValueError("Compose project name must be peak")
    return revision


def validate_manual_backup(receipt_path, now=None):
    now = time.time() if now is None else now
    receipt = json.loads(Path(receipt_path).read_text())
    created = receipt.get("verified_at")
    if not isinstance(created, (float, int)) or created > now or now - created > 86400:
        raise ValueError("Manual downloaded backup receipt must be verified within 24 hours")
    if receipt.get("authenticated_decryption") is not True or receipt.get("manifest_verified") is not True:
        raise ValueError("Manual backup needs local authenticated decryption and manifest verification")
    local_copy = receipt.get("local_copy")
    if not isinstance(local_copy, str) or not local_copy.startswith("/"):
        raise ValueError("Manual backup receipt must identify the persisted local copy")
    snapshot = Path(receipt["ciphertext_path"]).resolve()
    directory = MANUAL_BACKUP_DIR.resolve()
    if snapshot.parent != directory or snapshot.suffix != ".cms":
        raise ValueError("Manual backup must identify a private exported CMS ciphertext")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if receipt.get("ciphertext_sha256") != digest:
        raise ValueError("Manual backup ciphertext differs from verified local download")
    return digest


if __name__ == "__main__":
    try:
        if sys.argv[1] == "manual-backup":
            validate_manual_backup(sys.argv[2])
        else:
            validate_release(json.load(sys.stdin), sys.argv[1])
    except (ValueError, KeyError, IndexError, OSError, json.JSONDecodeError) as exc:
        print(f"Release preflight failed: {exc}", file=sys.stderr)
        sys.exit(1)
