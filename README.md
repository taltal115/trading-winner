# AI Trading System (trading-winner)

Modular, event-driven AI-assisted quantitative swing-trading platform (2–10 day holds, PDT-safe). The backend runs the full pipeline (ingest → features → signals → AI enrichment → risk → execution → outcomes); the frontend is a **read-only** dashboard that explains what the system decided.

Design docs live in [`docs/`](docs/). Binding rules for contributors and agents are in [`.cursor/rules.md`](.cursor/rules.md).

## Repository layout

```
trading-winner/
├── backend/          # Python 3.13 · FastAPI · pytest
│   ├── app/          # API, services, engines, repositories, workers
│   ├── tests/
│   ├── .env.example  # → copy to .env for local dev
│   └── Dockerfile
├── frontend/         # Next.js 16 · TypeScript · Tailwind (read-only UI)
│   ├── app/          # Dashboard pages
│   ├── lib/api.ts    # GET-only typed API client
│   └── .env.example  # → copy to .env.local
├── docs/             # Architecture, trading engine, database, deployment
└── .github/workflows/  # backend.yml, frontend.yml, scheduler.yml
```

## Prerequisites

| Tool | Version | Notes |
|------|---------|--------|
| **Python** | 3.13+ | Backend runtime and tests |
| **Node.js** | 20+ (22 tested) | Frontend dev server |
| **npm** | 10+ | Frontend dependencies |

Optional (only when you switch off mocks):

- **OpenAI API key** — `TW_AI_PROVIDER_BACKEND=openai`
- **IBKR TWS / Gateway** — `TW_BROKER_BACKEND=ibkr`, `TW_MARKET_DATA_BACKEND=ibkr`
- **Firestore** — `TW_REPOSITORY_BACKEND=firestore` (+ GCP credentials or emulator)

Local dev uses **in-memory storage** and **deterministic mocks** by default — no external accounts required.

## First-time setup

### 1. Backend

```bash
cd backend

# Virtual environment (once)
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install package + dev tools (lint, typecheck, pytest)
pip install ".[dev]"

# Environment (once) — defaults are fine for local mock mode
cp .env.example .env
```

Optional extras (install only if you need them):

```bash
pip install ".[firestore]"   # Firestore DocumentStore adapter
pip install ".[openai]"      # Live GPT + embeddings
pip install ".[ibkr]"        # Interactive Brokers adapters
```

### 2. Frontend

```bash
cd frontend

cp .env.example .env.local   # points at http://localhost:8000

npm install
```

If `npm install` fails with permission errors on macOS (e.g. `EACCES` on `~/.npm`), fix ownership once:

```bash
sudo chown -R "$(id -u)":"$(id -g)" ~/.npm
```

Then re-run `npm install`.

## Run locally

Use **two terminals** — backend first, then frontend.

### Terminal 1 — Backend (FastAPI)

```bash
cd backend
source .venv/bin/activate

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
# → {"status":"ok","environment":"dev","phase":1,...}
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Terminal 2 — Frontend (Next.js)

```bash
cd frontend
npm run dev
```

Open the dashboard: [http://localhost:3000](http://localhost:3000)

The UI fetches the backend from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). If the API is down, each page shows an “API unavailable” state instead of crashing.

## Populate data in dev

With defaults (`TW_PHASE=1`, mocks), trigger a pipeline run to generate signals:

```bash
cd backend && source .venv/bin/activate
curl -X POST http://localhost:8000/pipeline/run
curl http://localhost:8000/signals
```

Higher phases unlock more stages (AI, risk/execution, staging workers, learning loop). Set `TW_PHASE` in `backend/.env` and restart uvicorn:

| `TW_PHASE` | Name | What unlocks |
|------------|------|----------------|
| 1 | MVP read-only | Quant signals only (default) |
| 2 | Backtesting | `/backtests` walk-forward replay |
| 3 | AI integration | Catalyst + AI enrichment on signals |
| 4 | Risk + execution | Risk gate, paper trades, portfolio |
| 5 | Staging | Position monitor, trading guard, reconciliation |
| 6 | Production | Learning loop (`outcomes/`) on trade close |

Example — run the full mock pipeline through paper execution:

```bash
# in backend/.env
TW_PHASE=4
```

Restart uvicorn, then `POST /pipeline/run` and refresh the frontend **Portfolio** and **Trades** views.

## Environment variables (quick reference)

### Backend (`backend/.env`)

All settings use the `TW_` prefix. See [`backend/.env.example`](backend/.env.example) for the full list.

| Variable | Local default | Purpose |
|----------|---------------|---------|
| `TW_ENVIRONMENT` | `dev` | `dev` / `staging` / `prod` |
| `TW_PHASE` | `1` | Implementation phase gate (table above) |
| `TW_REPOSITORY_BACKEND` | `memory` | `memory` or `firestore` |
| `TW_AI_PROVIDER_BACKEND` | `mock` | `mock` or `openai` (+ `OPENAI_API_KEY`) |
| `TW_BROKER_BACKEND` | `mock` | `mock` or `ibkr` |
| `TW_MARKET_DATA_BACKEND` | `mock` | `mock` or `ibkr` |

### Frontend (`frontend/.env.local`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI base URL |

## Tests and quality checks

### Backend

```bash
cd backend
source .venv/bin/activate

ruff check app tests
black --check app tests
mypy app
pytest -q
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

CI runs the same checks via [`.github/workflows/backend.yml`](.github/workflows/backend.yml) and [`.github/workflows/frontend.yml`](.github/workflows/frontend.yml).

## Workers (optional, manual)

Scheduled jobs are defined in [`.github/workflows/scheduler.yml`](.github/workflows/scheduler.yml). Run them locally against the in-memory store:

```bash
cd backend && source .venv/bin/activate

python -m app.workers.daily_pipeline      # full daily pipeline
python -m app.workers.position_monitor    # live exits (phase 5+)
python -m app.workers.reconciliation      # broker drift check (phase 5+)
python -m app.workers.learning_job        # outcome backfill (phase 6+)
```

## Docker (backend only)

```bash
docker build -t trading-winner-backend backend/
docker run --rm -p 8000:8000 --env-file backend/.env trading-winner-backend
```

The image installs the Firestore extra; override env vars at runtime for your target environment.

## Documentation map

| Doc | Contents |
|-----|----------|
| [`docs/PROJECT.md`](docs/PROJECT.md) | Vision, principles, success criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layers, jobs, failure handling |
| [`docs/TRADING_ENGINE.md`](docs/TRADING_ENGINE.md) | Scoring, risk, exits |
| [`docs/AI_PIPELINE.md`](docs/AI_PIPELINE.md) | AI gating, RAG, cost control |
| [`docs/DATABASE.md`](docs/DATABASE.md) | Firestore collections and IDs |
| [`docs/UI.md`](docs/UI.md) | Read-only frontend contract |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Staging/prod, CI/CD, secrets |
| [`frontend/README.md`](frontend/README.md) | Frontend structure and scripts |

## Architecture (one line)

**API → Service → Engine → Repository** — engines are pure; AI enriches but never executes; risk is a deterministic gate; every trade is reconstructable end-to-end.
