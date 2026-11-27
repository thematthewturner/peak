"""Infrastructure tables carried over from Belay's hardened pattern.

Domain tables (items, attempts, tickets, ...) live in models.py. Migrations are additive only.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String)  # "student" (Addison) or "parent" (Matt)
    household: Mapped[str] = mapped_column(String, default="family")


class Login(Base):
    __tablename__ = "logins"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str] = mapped_column(String)
    expires: Mapped[str] = mapped_column(String)


class Throttle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window: Mapped[str] = mapped_column(String)


class Command(Base):
    """Idempotency keys for mutating requests."""

    __tablename__ = "commands"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String)
    request_hash: Mapped[str] = mapped_column(String)
    result_id: Mapped[str] = mapped_column(String)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String)
    ref_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created: Mapped[str] = mapped_column(String, default=now)


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    id: Mapped[str] = mapped_column(String, primary_key=True, default="worker")
    at: Mapped[str] = mapped_column(String, default=now)


class Job(Base):
    """Leased background job. One row per (ref_id, kind); a retry resets the row."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("ref_id", "kind"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    ref_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="pending")
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[str | None] = mapped_column(String, nullable=True)
    tries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created: Mapped[str] = mapped_column(String, default=now)


class ProviderCall(Base):
    """Per-request receipt that backs the monthly budget. Unavailable usage stays unknown."""

    __tablename__ = "provider_calls"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    household: Mapped[str] = mapped_column(String)
    ref_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)
    created: Mapped[str] = mapped_column(String, default=now)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, default="reserved", server_default="reserved")
    usage_known: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class JobEvent(Base):
    """Durable stage timeline for jobs: drives progress UI and latency metrics."""

    __tablename__ = "job_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(String, index=True)
    ref_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created: Mapped[str] = mapped_column(String, default=now)


class ErrorEvent(Base):
    """In-app error tracking: exception class and code frames only, never messages."""

    __tablename__ = "error_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    service: Mapped[str] = mapped_column(String)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_class: Mapped[str] = mapped_column(String)
    frames: Mapped[str] = mapped_column(Text, default="[]")
    created: Mapped[str] = mapped_column(String, default=now, index=True)


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
