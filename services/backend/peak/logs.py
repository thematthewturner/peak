"""Structured logs, stage events and in-app error tracking.

Privacy rule: only allowlisted, non-content fields leave this module. Prompts, model
outputs, student text, filenames, exception messages and secrets are never logged;
exceptions are reduced to their class plus code frames (file:line:function).
"""

import contextvars
import json
import logging
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

request_id = contextvars.ContextVar("peak_request_id", default=None)

# Fields a log line may carry. Anything else passed via `extra=` is dropped.
FIELDS = frozenset(
    {
        "service",
        "request_id",
        "method",
        "route",
        "status",
        "ms",
        "job_id",
        "ref_id",
        
        "source_id",
        
        "call_id",
        "kind",
        "stage",
        "model",
        "provider_request_id",
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "stop_reason",
        "outcome",
        "error_class",
        "frames",
        "round",
        "blocking",
        "minor",
        "pages",
        "chunks",
        "done",
        "total",
        "attempt",
        "questions",
    }
)
# Event detail stored in job_events and returned to the UI.
EVENT_FIELDS = frozenset(
    {"ms", "round", "blocking", "minor", "done", "total", "pages", "chunks", "questions", "model", "outcome"}
)
_SCALARS = (str, int, float, bool, type(None))
_service = "peak"


def _clean(value):
    if isinstance(value, _SCALARS):
        return value[:200] if isinstance(value, str) else value
    if isinstance(value, (list, tuple)) and all(isinstance(v, _SCALARS) for v in value):
        return [v[:200] if isinstance(v, str) else v for v in value][:30]
    return None


def frames(tb, limit=12):
    return [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in traceback.extract_tb(tb)][-limit:]


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": _service,
            # Peak messages are static strings with ids; third-party messages are capped.
            "event": record.getMessage()[:300],
        }
        current = request_id.get()
        if current:
            entry["request_id"] = current
        for key in FIELDS:
            if key in record.__dict__ and key not in entry:
                cleaned = _clean(record.__dict__[key])
                if cleaned is not None:
                    entry[key] = cleaned
        if record.exc_info and record.exc_info[0] is not None:
            entry["error_class"] = record.exc_info[0].__name__
            entry["frames"] = frames(record.exc_info[2])
        return json.dumps(entry, separators=(",", ":"))


def setup(service):
    """Configure root logging once per process."""
    global _service
    _service = service
    handler = logging.StreamHandler(sys.stdout)
    if config.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(config.LOG_LEVEL)
    # httpx logs every request line at INFO; provider calls are logged by Peak instead.
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def emit(job_id, stage, *, ref_id=None, **detail):
    """Record a job stage durably and as a log line. Never raises."""
    from .db import SessionLocal, JobEvent

    kept = {k: v for k, v in detail.items() if k in EVENT_FIELDS and _clean(v) is not None}
    logging.getLogger("peak.jobs").info(
        "job stage", extra={"job_id": job_id, "ref_id": ref_id, "stage": stage, **kept}
    )
    try:
        with SessionLocal() as db:
            db.add(JobEvent(job_id=job_id, ref_id=ref_id, stage=stage, detail=json.dumps(kept)))
            db.commit()
    except Exception:  # Progress is best-effort; a failed write must not fail the job.
        logging.getLogger("peak.jobs").warning("job event write failed", exc_info=True)


def record_error(error, *, route=None, job_id=None):
    """Persist an exception class and frames for diagnosis. Never raises."""
    from .db import SessionLocal, ErrorEvent

    try:
        with SessionLocal() as db:
            db.add(
                ErrorEvent(
                    service=_service,
                    request_id=request_id.get(),
                    route=route,
                    job_id=job_id,
                    error_class=type(error).__name__,
                    frames=json.dumps(frames(error.__traceback__)),
                )
            )
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            db.query(ErrorEvent).filter(ErrorEvent.created < cutoff).delete()
            db.commit()
    except Exception:
        logging.getLogger("peak").warning("error event write failed", exc_info=True)


def job_progress(db, job):
    """Stages recorded since the job's latest (re)queue, for the UI."""
    from sqlalchemy import select
    from .db import JobEvent

    rows = db.scalars(
        select(JobEvent)
        .where(JobEvent.job_id == job.id, JobEvent.created >= job.created)
        .order_by(JobEvent.created, JobEvent.id)
    ).all()
    return [{"stage": r.stage, "at": r.created, **json.loads(r.detail)} for r in rows]
