# Peak

SAT prep for Addison. Find the points she's still losing, fix them once, prove it on a question she's never seen.

- Plan: [`docs/PRD.md`](docs/PRD.md) · Build status: [`docs/STATUS.md`](docs/STATUS.md)
- Deployment (owner steps, nothing automatic): [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- Private corpus rules and import: [`docs/DATA.md`](docs/DATA.md)

## Develop

```bash
cd services/backend
uv sync && uv run alembic upgrade head
PEAK_DEMO=1 uv run uvicorn peak.api:app --port 8000     # demo logins: student/peak-student-demo, parent/peak-parent-demo
uv run pytest -q && uv run ruff check peak tests
```

```bash
cd apps/web
npm ci && API_INTERNAL_URL=http://127.0.0.1:8000 npm run dev
npm run typecheck && npm run lint && npm test
```

The repo ships with zero official content.
