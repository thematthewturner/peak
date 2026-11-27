import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def test_no_sqlite_only_boolean_defaults():
    """Autogenerating on SQLite renders boolean defaults as text('0'/'1'), which Postgres rejects
    (DatatypeMismatch). Migrations must use sa.false()/sa.true()."""
    bad = []
    for path in VERSIONS.glob("*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"sa\.Boolean\(\).*server_default=sa\.text\(['\"][01]['\"]\)", line):
                bad.append(f"{path.name}:{n}")
    assert not bad, f"use sa.false()/sa.true() for boolean defaults: {bad}"
