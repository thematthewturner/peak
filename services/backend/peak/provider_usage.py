"""Durable per-request receipts; unavailable provider usage stays unknown."""

from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
import logging
import threading
import time
from sqlalchemy import update, select
from . import config
from .db import ProviderCall, Job, SessionLocal, User, now

log = logging.getLogger("peak.provider")


class ProviderBudgetFailure(ValueError):
    """No paid inference has started when preflight rejects a request."""


# USD per million input/output tokens for known Claude models (list prices, 2026-11).
# Environment rates override these; unknown models keep cost unknown (0).
KNOWN_RATES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-fable-5-1": (10.0, 50.0),
}


def model_rates(model_id):
    separate_checker = bool(config.MODEL_CHECK_ID) and model_id == config.MODEL_CHECK_ID != config.MODEL_ID
    if separate_checker:
        configured = (config.MODEL_CHECK_INPUT_USD_PER_MILLION, config.MODEL_CHECK_OUTPUT_USD_PER_MILLION)
    else:
        configured = (config.MODEL_INPUT_USD_PER_MILLION, config.MODEL_OUTPUT_USD_PER_MILLION)
    if configured[0] > 0 and configured[1] > 0:
        return configured
    return KNOWN_RATES.get(model_id, (0.0, 0.0))


def rates(checker, model_id=None):
    """Kept for callers that only know whether a call is the checker."""
    if model_id:
        return model_rates(model_id)
    model_id = (config.MODEL_CHECK_ID or config.MODEL_ID) if checker else config.MODEL_ID
    return model_rates(model_id)


def preflight(client, call_id, checker, kwargs):
    if not call_id:
        return
    with SessionLocal() as db:
        stored = db.get(ProviderCall, call_id)
        if stored is None:
            # Unit doubles and legacy receipts have no stored reservation.
            return
    try:
        counted = client.messages.count_tokens(
            **{key: kwargs[key] for key in ("model", "messages", "system", "output_format") if key in kwargs}
        )
        input_tokens = counted.input_tokens
        if not isinstance(input_tokens, int) or input_tokens < 0:
            raise ValueError("Invalid provider token count")
    except Exception:
        # count_tokens is a preflight request, never inference. This reservation
        # is known unused; callers must not fall back to an uncounted paid call.
        fail_running_receipts({"preflight": call_id})
        raise ProviderBudgetFailure(
            "The model token preflight did not finish. Retry explicitly; no model inference was started."
        ) from None
    reservation = input_tokens + kwargs["max_tokens"] + 1024
    with SessionLocal() as db:
        row = db.get(ProviderCall, call_id)
        db.scalar(
            select(User).where(User.household == row.household).order_by(User.id).limit(1).with_for_update()
        )
        started_at = now()
        # Charge the inference month, rather than the month a queued job was
        # requested. The job still retains its original request date.
        row.created = started_at
        calls = db.scalars(
            select(ProviderCall).where(
                ProviderCall.household == row.household, ProviderCall.created.like(started_at[:7] + "%")
            )
        ).all()
        others = [
            call
            for call in calls
            if call.id != call_id
            and not (
                call.state == "failed"
                and call.usage_known
                and call.input_tokens == 0
                and call.output_tokens == 0
            )
        ]
        used_tokens = sum(
            (call.input_tokens or 0) + (call.output_tokens or 0)
            if call.usage_known
            else max(call.reserved_tokens, 80000)
            for call in others
        )
        input_rate, output_rate = rates(checker, kwargs["model"])
        check_rates = rates(True)
        max_rate = max(
            input_rate,
            output_rate,
            *rates(False),
            *check_rates,
        )
        used_cost = sum(
            call.cost_usd
            if call.cost_usd is not None
            else max(call.reserved_tokens, 80000) * max_rate / 1_000_000
            for call in others
        )
        request_limit = len(others) + 1 > config.PEAK_REQUEST_LIMIT_MONTH
        if (
            request_limit
            or used_tokens + reservation > config.PEAK_TOKEN_LIMIT_MONTH
            or (
                input_rate > 0
                and output_rate > 0
                and used_cost + reservation * max_rate / 1_000_000 > config.PEAK_COST_LIMIT_MONTH
            )
        ):
            row.state, row.usage_known = "failed", True
            row.input_tokens = row.output_tokens = 0
            row.cost_usd = 0
            db.commit()
            raise ProviderBudgetFailure(
                "Peak has reached its monthly AI request limit. No model inference was started."
                if request_limit
                else "This request would exceed Peak's monthly AI budget. No model inference was started."
            )
        row.reserved_tokens = reservation
        row.model_id = kwargs["model"]
        db.commit()


def receipt(call_id, *, state, model_id, usage=None, checker=False):
    if not call_id:
        return
    with SessionLocal() as db:
        row = db.get(ProviderCall, call_id)
        if row is None:
            return
        row.state = state
        row.model_id = model_id
        if usage is not None:
            row.input_tokens = (
                int(usage.input_tokens)
                + int(getattr(usage, "cache_read_input_tokens", 0) or 0)
                + int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
            )
            row.output_tokens = int(usage.output_tokens)
            row.usage_known = True
            input_rate, output_rate = rates(checker, model_id)
            # Cache rates differ across providers: this is a configured conservative
            # estimate, not a fabricated exact invoice. Unconfigured rates stay null.
            if input_rate > 0 and output_rate > 0:
                row.cost_usd = (row.input_tokens * input_rate + row.output_tokens * output_rate) / 1_000_000
        db.commit()


def _complete(client, kwargs):
    """Stream so long generations never hit an idle-read timeout; return the final message."""
    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()
        if getattr(message, "_request_id", None) is None:
            with suppress(Exception):
                message._request_id = stream.response.headers.get("request-id")
    return message


def parse_with_receipt(client, *, call_id, checker=False, stage=None, job_id=None, **kwargs):
    preflight(client, call_id, checker, kwargs)
    receipt(call_id, state="running", model_id=kwargs["model"])
    started = time.monotonic()
    try:
        result = _complete(client, kwargs)
    except Exception as error:
        receipt(
            call_id,
            state="failed",
            model_id=kwargs["model"],
            usage=getattr(error, "usage", None),
            checker=checker,
        )
        log.warning(
            "model call failed",
            extra={
                "job_id": job_id,
                "call_id": call_id,
                "stage": stage,
                "model": kwargs["model"],
                "ms": round((time.monotonic() - started) * 1000),
                "error_class": type(error).__name__,
                "status": getattr(error, "status_code", None),
            },
        )
        raise
    usage = getattr(result, "usage", None)
    receipt(call_id, state="done", model_id=kwargs["model"], usage=usage, checker=checker)
    log.info(
        "model call",
        extra={
            "job_id": job_id,
            "call_id": call_id,
            "stage": stage,
            "model": kwargs["model"],
            "ms": round((time.monotonic() - started) * 1000),
            "stop_reason": getattr(result, "stop_reason", None),
            "provider_request_id": getattr(result, "_request_id", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
        },
    )
    return result


def new_call(household, kind, ref_id=None):
    """A budget receipt for a call decided inside the worker."""
    with SessionLocal() as db:
        call = ProviderCall(household=household, ref_id=ref_id, kind=kind, reserved_tokens=80000)
        db.add(call)
        db.commit()
        return call.id


@contextmanager
def lease_heartbeat(job_id):
    stop = threading.Event()

    def pulse():
        while not stop.wait(20):
            try:
                with SessionLocal() as db:
                    changed = db.execute(
                        update(Job)
                        .where(Job.id == job_id, Job.state == "running")
                        .values(
                            lease_until=(
                                datetime.now(timezone.utc) + timedelta(seconds=config.JOB_LEASE_SECONDS)
                            ).isoformat()
                        )
                    ).rowcount
                    db.commit()
                    if not changed:
                        break
            except Exception as error:
                log.warning("Lease heartbeat failed for %s (%s)", job_id, type(error).__name__)

    thread = threading.Thread(target=pulse, name="peak-job-lease", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2)


def no_request_started(call_ids):
    """True when every receipt is still reserved, so no provider request was made.

    parse_with_receipt moves a receipt to "running" before it calls the provider,
    so a job whose receipts are all "reserved" cannot have been charged and may
    safely be run again. An empty mapping also means nothing was started.
    """
    with SessionLocal() as db:
        return all(
            (row := db.get(ProviderCall, call_id)) is None or row.state == "reserved"
            for call_id in call_ids.values()
        )


def fail_running_receipts(call_ids):
    """An interrupted worker cannot claim zero billing or silently replay a call."""
    with SessionLocal() as db:
        for call_id in call_ids.values():
            row = db.get(ProviderCall, call_id)
            if row is not None and row.state == "running":
                row.state = "failed"
            elif row is not None and row.state == "reserved":
                # No provider request started: this is a known zero, unlike an
                # interrupted network request whose billing cannot be established.
                row.state = "failed"
                row.usage_known = True
                row.input_tokens = row.output_tokens = 0
                row.cost_usd = 0
        db.commit()
