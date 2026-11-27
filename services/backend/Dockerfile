# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
COPY --chown=10001:10001 pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then SSL_CERT_FILE=/run/secrets/proxy_ca uv sync --frozen --no-dev; else uv sync --frozen --no-dev; fi
COPY --chown=10001:10001 peak ./peak
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 migrations ./migrations
RUN groupadd -g 10001 peak && useradd -u 10001 -g peak peak && mkdir /data && chown peak:peak /data
ENV PATH="/app/.venv/bin:$PATH" DATA_DIR=/data
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "peak.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
