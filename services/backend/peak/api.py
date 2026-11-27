import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import config, logs
from .auth import DUMMY_HASH, authenticate, create_login, digest, passwords, slide_session
from .db import Heartbeat, Job, Login, SessionLocal, Throttle, User, get_db, now


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        if config.DEMO:
            for role in ("parent", "student"):
                if not db.scalar(select(User).where(User.username == role)):
                    db.add(User(username=role, role=role, password_hash=passwords.hash(f"peak-{role}-demo")))
        db.commit()
    yield


app = FastAPI(title="Peak", lifespan=lifespan)


@app.middleware("http")
async def security(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("origin") != config.BASE_URL:
            return Response("Origin not allowed", status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


access_log = logging.getLogger("peak.http")
logs.setup("api")


@app.middleware("http")
async def observe(request, call_next):
    """Outermost: every response carries a reference the UI can show and logs can find."""
    rid = uuid.uuid4().hex[:12]
    token = logs.request_id.set(rid)
    started = time.perf_counter()
    status = 500
    try:
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as error:
            route = getattr(request.scope.get("route"), "path", None)
            access_log.error("unhandled error", exc_info=True, extra={"route": route})
            logs.record_error(error, route=route)
            response = JSONResponse(
                {"detail": f"Something went wrong. Reference {rid}.", "ref": rid}, status_code=500
            )
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", None) or "unmatched"
        level = logging.DEBUG if route in ("/api/health", "/api/readiness") else logging.INFO
        access_log.log(
            level,
            "request",
            extra={
                "method": request.method,
                "route": route,
                "status": status,
                "ms": round((time.perf_counter() - started) * 1000),
            },
        )
        logs.request_id.reset(token)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


WINDOW = timedelta(minutes=15)


def _bump(db, key, current):
    row = db.get(Throttle, key)
    if not row:
        row = Throttle(key=key, failures=0, window=now())
        db.add(row)
    if datetime.fromisoformat(row.window) <= current - WINDOW:
        row.window, row.failures = now(), 0
    row.failures += 1


def _locked(row, limit, current):
    return bool(row and datetime.fromisoformat(row.window) > current - WINDOW and row.failures >= limit)


@app.post("/api/login")
def login(body: Credentials, request: Request, response: Response, db=Depends(get_db)):
    # Uvicorn accepts forwarded addresses only from the configured edge proxy IP.
    ip_key = digest("ip:" + (request.client.host if request.client else "unknown"))
    account_key = digest("account:" + body.username.casefold())
    current = datetime.now(timezone.utc)
    if _locked(db.get(Throttle, ip_key), 8, current):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    if _locked(db.get(Throttle, account_key), 32, current):
        raise HTTPException(429, "Too many attempts for this account. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.username == body.username))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        _bump(db, ip_key, current)
        _bump(db, account_key, current)
        db.commit()
        raise HTTPException(401, "Username or password did not match")
    for key in (ip_key, account_key):
        if row := db.get(Throttle, key):
            db.delete(row)
    csrf = create_login(db, user, response)
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role, "csrf": csrf}


@app.post("/api/logout")
def logout(request: Request, response: Response, user=Depends(authenticate), db=Depends(get_db)):
    db.delete(db.get(Login, request.state.login.token_hash))
    db.commit()
    response.delete_cookie("peak_session", path="/")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request, response: Response, user=Depends(authenticate), db=Depends(get_db)):
    slide_session(db, request, response, user)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "csrf": request.state.login.csrf,
        "demo": config.DEMO,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/readiness")
def readiness(db=Depends(get_db)):
    db.execute(select(1))
    beat = db.get(Heartbeat, "worker")
    stale = not beat or beat.at < (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    oldest = db.scalar(select(func.min(Job.created)).where(Job.state.in_(["pending", "running"])))
    ready = not stale
    body = {"status": "ok" if ready else "degraded", "worker_stale": stale, "oldest_pending_job": oldest}
    return JSONResponse(body, status_code=200 if ready else 503)
