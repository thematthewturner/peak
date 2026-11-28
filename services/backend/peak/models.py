"""Domain tables (PRD s9.3). Attempts, events and ticket evidence are append-only."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now, uid


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    section: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String, index=True)
    skill: Mapped[str] = mapped_column(String)
    micro_skill: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    domain_weight: Mapped[float] = mapped_column(Float, default=0.0)
    cue: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    sha256: Mapped[str] = mapped_column(String, unique=True)
    kind: Mapped[str] = mapped_column(String)  # qbank_export|practice_test|bluebook_screens|book_scan|scratch
    rights: Mapped[str] = mapped_column(String, default="private_official")
    export_filter_json: Mapped[str] = mapped_column(Text, default="{}")
    path: Mapped[str] = mapped_column(Text)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="uploaded")
    created: Mapped[str] = mapped_column(String, default=now)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("origin", "source_ref"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    origin: Mapped[str] = mapped_column(String)  # official|template|generated
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # Question ID
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True, index=True)
    family_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String, nullable=True)  # easy|medium|hard
    format: Mapped[str] = mapped_column(String)  # mc|numeric
    benchmark_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|review|verified|pulled
    rights: Mapped[str] = mapped_column(String, default="private_official")
    content: Mapped[str] = mapped_column(Text, default="{}")  # passage, stem, choices
    key: Mapped[str] = mapped_column(Text, default="[]")  # accepted answers; never sent pre-attempt
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[str] = mapped_column(String, default=now)


class ItemAsset(Base):
    __tablename__ = "item_assets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # figure|page_crop
    path: Mapped[str] = mapped_column(Text)


class ItemCheck(Base):
    __tablename__ = "item_checks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    check: Mapped[str] = mapped_column(String)  # schema|key_present|blind_solve|sympy|text_match|figure
    passed: Mapped[bool] = mapped_column(Boolean)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    receipt_id: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created: Mapped[str] = mapped_column(String, default=now)


class Form(Base):
    """The form ledger: which Bluebook / paper forms are unseen, reserved, used or exposed."""

    __tablename__ = "forms"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    label: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="unseen")  # unseen|reserved|used|exposed


class Benchmark(Base):
    __tablename__ = "benchmarks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    form_id: Mapped[str | None] = mapped_column(ForeignKey("forms.id"), nullable=True)
    series: Mapped[str] = mapped_column(String)  # psat|bluebook_clean|bluebook_exposed|official_sat
    taken_on: Mapped[str] = mapped_column(String)
    rw_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    math_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    m2_tiers: Mapped[str] = mapped_column(Text, default="{}")
    conditions: Mapped[str] = mapped_column(Text, default="{}")  # unseen, single_sitting, uninterrupted, unaided
    clean: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    domain_bands: Mapped[str] = mapped_column(Text, default="{}")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String)  # drill|review|timed|cards
    mode: Mapped[str] = mapped_column(String, default="learning")  # learning|timed
    minutes: Mapped[int] = mapped_column(Integer, default=25)
    plan: Mapped[str] = mapped_column(Text, default="[]")  # composer blocks with reasons
    started: Mapped[str] = mapped_column(String, default=now)
    ended: Mapped[str | None] = mapped_column(String, nullable=True)
    usefulness: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Attempt(Base):
    """Append-only. A retry creates a new row; idempotency_key dedupes double submits."""

    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    item_version: Mapped[int] = mapped_column(Integer, default=1)
    params: Mapped[str] = mapped_column(Text, default="{}")  # template parameters, if any
    first_exposure: Mapped[bool] = mapped_column(Boolean, default=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)  # null = skipped
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)  # sure|unsure|guess
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flags: Mapped[str] = mapped_column(Text, default="{}")  # flagged, answer_changes, desmos_used, aided
    cold_retry: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String)
    created: Mapped[str] = mapped_column(String, default=now)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)
    data: Mapped[str] = mapped_column(Text, default="{}")
    created: Mapped[str] = mapped_column(String, default=now)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), index=True)
    origin_attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    cause: Mapped[str] = mapped_column(String)
    micro_skill: Mapped[str | None] = mapped_column(String, nullable=True)
    cue: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String, default="OPEN", index=True)
    intervention: Mapped[str | None] = mapped_column(String, nullable=True)
    repaired_at: Mapped[str | None] = mapped_column(String, nullable=True)
    next_due: Mapped[str | None] = mapped_column(String, nullable=True)
    timing_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Her one-line fix rule in her own words (score guide s4.4): a light self-explanation, reviewed as a card.
    rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    created: Mapped[str] = mapped_column(String, default=now)


class TicketEvidence(Base):
    __tablename__ = "ticket_evidence"
    __table_args__ = (UniqueConstraint("ticket_id", "attempt_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    counted: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String)
    created: Mapped[str] = mapped_column(String, default=now)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # formula|grammar|transition|desmos|cue
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(Text, default="{}")  # serialized py-fsrs Card
    due: Mapped[str] = mapped_column(String, default=now, index=True)


class CardReview(Base):
    __tablename__ = "card_reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 again, 2 hard, 3 good, 4 easy
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created: Mapped[str] = mapped_column(String, default=now)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    target_total: Mapped[int] = mapped_column(Integer, default=1400)
    target_date: Mapped[str] = mapped_column(String, default="2027-06-05")
    cadence: Mapped[str] = mapped_column(Text, default='{"sessions_per_week": 3, "minutes": 25}')
    math_share: Mapped[float] = mapped_column(Float, default=0.6)


class SchoolTest(Base):
    __tablename__ = "school_tests"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    on_date: Mapped[str] = mapped_column(String)
