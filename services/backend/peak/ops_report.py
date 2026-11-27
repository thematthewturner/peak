"""Operator commands that print counts only (never item text, answers or filenames).

Run inside the api container:
  python -m peak.ops_report drain     ask the worker to claim no new jobs (deploys)
  python -m peak.ops_report running   print the number of jobs actively running
"""
import sys

from sqlalchemy import func, select

from .db import Heartbeat, Job, SessionLocal, now


def running_jobs(db):
    return db.scalar(
        select(func.count()).select_from(Job).where(Job.state == "running", Job.lease_until > now())
    ) or 0


def request_drain(db):
    row = db.get(Heartbeat, "drain")
    if row:
        row.at = now()
    else:
        db.add(Heartbeat(id="drain", at=now()))
    db.commit()


def main(argv):
    if argv and argv[0] == "drain":
        with SessionLocal() as db:
            request_drain(db)
        return
    if argv and argv[0] == "running":
        with SessionLocal() as db:
            print(running_jobs(db))
        return
    raise SystemExit("usage: python -m peak.ops_report drain | running")


if __name__ == "__main__":
    main(sys.argv[1:])
