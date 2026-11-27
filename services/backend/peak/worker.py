"""Background worker: heartbeat, drain, housekeeping, and a job registry.

Job handlers register in HANDLERS as work packages land (ingest, generation, scratch work).
"""
import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from . import logs
from .db import Heartbeat, Login, SessionLocal, now

log = logging.getLogger("peak.worker")

HOUSEKEEPING_SECONDS = 24 * 3600
DRAIN_ID = "drain"
DRAIN_FRESH = timedelta(minutes=15)

# kind -> callable() -> bool (True when it did work). Filled in by later work packages.
HANDLERS: dict = {}


def draining(db=None):
    """True while a deploy has asked the worker to claim no new jobs."""

    def check(session):
        row = session.get(Heartbeat, DRAIN_ID)
        return bool(row and row.at > (datetime.now(timezone.utc) - DRAIN_FRESH).isoformat())

    if db is not None:
        return check(db)
    with SessionLocal() as session:
        return check(session)


def clear_drain():
    """A freshly started worker is the new release: it must not inherit the old drain request."""
    with SessionLocal() as db:
        db.execute(delete(Heartbeat).where(Heartbeat.id == DRAIN_ID))
        db.commit()


def work_once():
    if draining():
        return False
    return any(handler() for handler in HANDLERS.values())


def housekeeping():
    """Delete expired logins. Error events are pruned as they are written (logs.record_error)."""
    with SessionLocal() as db:
        removed = db.execute(delete(Login).where(Login.expires < now())).rowcount
        db.commit()
    log.info("housekeeping", extra={"outcome": f"expired_logins={removed}"})
    return removed


def main():
    logs.setup("worker")
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def keep_alive():
        while not stopping:
            with SessionLocal() as db:
                beat = db.get(Heartbeat, "worker")
                if beat:
                    beat.at = now()
                else:
                    db.add(Heartbeat(id="worker", at=now()))
                db.commit()
            time.sleep(10)

    clear_drain()
    with SessionLocal() as db:
        if not db.get(Heartbeat, "worker"):
            db.add(Heartbeat(id="worker", at=now()))
            db.commit()
    threading.Thread(target=keep_alive, daemon=True).start()
    next_housekeeping = 0.0
    while not stopping:
        if time.monotonic() >= next_housekeeping:
            try:
                housekeeping()
            except Exception as error:  # Housekeeping must never stop job work.
                log.warning("Housekeeping failed", exc_info=True)
                logs.record_error(error)
            next_housekeeping = time.monotonic() + HOUSEKEEPING_SECONDS
        if not work_once():
            time.sleep(1)


if __name__ == "__main__":
    main()
