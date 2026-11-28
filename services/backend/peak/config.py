import os
from pathlib import Path

DEMO = os.getenv("PEAK_DEMO", "0") == "1"
PRODUCTION = os.getenv("PEAK_ENV", "development") == "production"
if PRODUCTION and DEMO:
    raise RuntimeError("Demo accounts are forbidden in production")
BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
if PRODUCTION and not BASE_URL.startswith("https://"):
    raise RuntimeError("Production requires an HTTPS APP_BASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./.data/peak.db")
DATA_DIR = Path(os.getenv("DATA_DIR", ".data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_BYTES", "33554432"))

# Models. MODEL_ID drafts and extracts; MODEL_CHECK_ID blind-solves (PRD s8.6).
MODEL_ID = os.getenv("MODEL_ID", "").strip() or "claude-sonnet-5-5"
MODEL_CHECK_ID = os.getenv("MODEL_CHECK_ID", "").strip()
MODEL_INPUT_USD_PER_MILLION = float(os.getenv("MODEL_INPUT_USD_PER_MILLION", "0"))
MODEL_OUTPUT_USD_PER_MILLION = float(os.getenv("MODEL_OUTPUT_USD_PER_MILLION", "0"))
MODEL_CHECK_INPUT_USD_PER_MILLION = float(os.getenv("MODEL_CHECK_INPUT_USD_PER_MILLION", "0"))
MODEL_CHECK_OUTPUT_USD_PER_MILLION = float(os.getenv("MODEL_CHECK_OUTPUT_USD_PER_MILLION", "0"))

# Monthly budget, enforced before every provider call (PRD s8.6). Ingestion has its own cap.
PEAK_COST_LIMIT_MONTH = float(os.getenv("PEAK_COST_LIMIT_MONTH", "20"))
PEAK_REQUEST_LIMIT_MONTH = int(os.getenv("PEAK_REQUEST_LIMIT_MONTH", "2000"))
PEAK_TOKEN_LIMIT_MONTH = int(os.getenv("PEAK_TOKEN_LIMIT_MONTH", "20000000"))
INGEST_COST_LIMIT = float(os.getenv("INGEST_COST_LIMIT", "200"))

JOB_LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "300"))
PROVIDER_TIMEOUT_SECONDS = int(os.getenv("PROVIDER_TIMEOUT_SECONDS", "600"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/New_York")

# Local Mac mode (python -m peak.local): one process serves the app and its data on 127.0.0.1.
LOCAL = os.getenv("PEAK_LOCAL", "0") == "1"
LOCAL_TOKEN = os.getenv("PEAK_LOCAL_TOKEN", "")
LOCAL_STUDENT = os.getenv("PEAK_LOCAL_STUDENT", "addison")
WEB_DIR = os.getenv("PEAK_WEB_DIR", "")
