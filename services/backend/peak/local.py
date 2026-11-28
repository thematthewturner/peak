"""Run Peak on this Mac. One process serves the app and its data on 127.0.0.1; nothing leaves the machine.

    python -m peak.local                 open Peak (native window if pywebview is installed, else the browser)
    python -m peak.local import FILE     load a Question Bank export into this Mac's Peak
    python -m peak.local where           show where data lives and what's in it
    python -m peak.local backup          copy the database to a dated file (keeps the last 14)
    python -m peak.local add-parent NAME create a parent sign-in (asks for a password)

Data lives in ~/Library/Application Support/Peak on a Mac (never in iCloud-synced Documents).
Everything that touches the database is imported only after the environment is configured.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

DEFAULT_PORT = 8765
REPO = Path(__file__).resolve().parents[3]


def default_home() -> Path:
    if os.getenv("PEAK_HOME"):
        return Path(os.environ["PEAK_HOME"]).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Peak"
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "peak"


def free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No free local port")


def configure(home: Path, port: int) -> str:
    """Set the environment peak.config reads. Must run before anything imports peak.config or peak.db."""
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = secrets.token_urlsafe(32)
    os.environ.update({
        "PEAK_LOCAL": "1",
        "PEAK_LOCAL_TOKEN": token,
        "DATA_DIR": str(home / "files"),
        "DATABASE_URL": f"sqlite:///{home / 'peak.db'}",
        "APP_BASE_URL": f"http://127.0.0.1:{port}",
        "PEAK_WEB_DIR": os.getenv("PEAK_WEB_DIR") or str(REPO / "apps" / "web" / "out"),
        "LOG_FORMAT": os.getenv("LOG_FORMAT", "text"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "WARNING"),
    })
    return token


def prepare(student: str) -> None:
    """Migrate, seed the skill tree, and make sure the student account exists."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(cfg, "head")

    from .auth import passwords
    from .db import SessionLocal, User
    from .seed import seed_skills

    with SessionLocal() as db:
        seed_skills(db)
        if not db.scalar(select(User).where(User.username == student)):
            # Opening Peak uses the launcher's one-time token; this password is random and never shown.
            db.add(User(username=student, role="student", password_hash=passwords.hash(secrets.token_urlsafe(24))))
            db.commit()


def counts() -> dict:
    from sqlalchemy import func, select

    from .db import SessionLocal
    from .models import Attempt, Item, Ticket

    with SessionLocal() as db:
        return {
            "questions_ready": db.scalar(select(func.count()).select_from(Item).where(Item.status == "verified")) or 0,
            "questions_held": db.scalar(select(func.count()).select_from(Item).where(Item.status != "verified")) or 0,
            "answers": db.scalar(select(func.count()).select_from(Attempt)) or 0,
            "fixes": db.scalar(select(func.count()).select_from(Ticket)) or 0,
        }


def backup(home: Path, keep: int = 14) -> Path:
    """Consistent copy via SQLite's online backup API, safe while Peak is open."""
    folder = home / "backups"
    folder.mkdir(exist_ok=True, mode=0o700)
    target = folder / f"peak-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(home / "peak.db") as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    for old in sorted(folder.glob("peak-*.db"))[:-keep]:
        old.unlink()
    return target


def serve(port: int):
    import uvicorn

    from .api import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            return server, thread
        time.sleep(0.05)
    raise RuntimeError("Peak's local engine did not start")


def open_window(url: str, *, window: bool) -> None:
    if window:
        try:
            import webview  # pywebview: a native Mac window using the system's WebKit
        except ImportError:
            webview = None
        if webview is not None:
            webview.create_window("Peak", url, width=1240, height=820, min_size=(960, 640))
            webview.start()
            return
    import webbrowser

    webbrowser.open(url)
    print(f"Peak is open in your browser. Keep this window running; press Ctrl+C to quit.\n{url.split('/api')[0]}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="peak", description="Peak, on this Mac")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "import", "where", "backup", "prepare", "add-parent"])
    parser.add_argument("file", nargs="?")
    parser.add_argument("--home", type=Path, default=None, help="data folder (default: Application Support/Peak)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--student", default=os.getenv("PEAK_LOCAL_STUDENT", "addison"))
    parser.add_argument("--no-window", action="store_true", help="serve only; print the address instead of opening it")
    parser.add_argument("--reprocess", action="store_true", help="import: re-run an already imported file")
    args = parser.parse_args(argv)

    home = (args.home or default_home()).expanduser().resolve()
    port = free_port(args.port) if args.command == "run" else args.port
    os.environ["PEAK_LOCAL_STUDENT"] = args.student
    token = configure(home, port)
    prepare(args.student)

    if args.command == "prepare":
        print(json.dumps({"home": str(home), **counts()}))
        return
    if args.command == "where":
        print(json.dumps({"home": str(home), "database": str(home / "peak.db"),
                          "web": os.environ["PEAK_WEB_DIR"], **counts()}, indent=1))
        return
    if args.command == "backup":
        print(backup(home))
        return
    if args.command == "add-parent":
        if not args.file:
            raise SystemExit("Usage: python -m peak.local add-parent NAME")
        from .manage import main as manage_main

        manage_main([args.file, "--role", "parent"])
        return
    if args.command == "import":
        if not args.file:
            raise SystemExit("Usage: python -m peak.local import FILE.jsonl")
        from .qbank import main as qbank_main

        qbank_main([args.file] + (["--reprocess"] if args.reprocess else []))
        print(json.dumps(counts()))
        return

    if not Path(os.environ["PEAK_WEB_DIR"], "index.html").exists():
        raise SystemExit("The app's screens aren't built yet. Run: (cd apps/web && npm ci && npm run build)")
    try:
        backup(home)  # one quiet backup per launch
    except sqlite3.Error:
        pass
    server, _ = serve(port)
    url = f"http://127.0.0.1:{port}/api/local/enter?t={token}"
    if args.no_window:
        print(url, flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        open_window(url, window=True)
    server.should_exit = True


if __name__ == "__main__":
    main()
