# AI Trading Intelligence — Frontend

A **strictly read-only** monitoring dashboard for the AI-assisted quantitative
swing-trading system. It visualizes signals, portfolio/positions, trades,
backtests, AI reasoning, and live trading-safety status by consuming the
FastAPI backend's **GET** endpoints only.

> The UI never decides or mutates trades — it explains them. There are no
> buttons, forms, or requests that change backend state (no pipeline runs, no
> trading halt/resume, no position-monitor triggers).

## Tech stack

- [Next.js 16](https://nextjs.org) (App Router) + TypeScript
- React Server Components for data fetching
- Tailwind CSS v4
- ESLint + Prettier

## Project structure

```
frontend/
├── app/                      # App Router pages (one folder per view)
│   ├── layout.tsx            # Root layout + sidebar nav
│   ├── page.tsx              # Dashboard (health, integrity, trading status)
│   ├── signals/page.tsx      # Ranked signals + AI enrichment
│   ├── portfolio/page.tsx    # Portfolio, positions, reconciliation
│   ├── trades/page.tsx       # Trade history
│   ├── backtests/page.tsx    # Backtest metrics
│   └── ai/
│       ├── page.tsx          # AI analyses list
│       └── [id]/page.tsx     # AI analysis detail
├── components/               # Sidebar, domain badges, UI primitives
│   └── ui/                   # Card, Badge, Table, StatCard, States, ...
└── lib/
    ├── types.ts              # TS types mirroring backend pydantic models
    ├── api.ts                # Centralized, typed, GET-only API client
    └── format.ts             # Presentation helpers (currency, %, dates)
```

### API client & types

All network access goes through `lib/api.ts`, a single typed client that
**only** issues HTTP GET requests. Each method returns an `ApiResult<T>`
(`{ ok: true, data }` or `{ ok: false, error }`) so pages render friendly
"API unavailable" states instead of crashing when the backend is down.

Types in `lib/types.ts` are hand-written to mirror the backend pydantic models
(`backend/app/models/entities.py`, `ai.py`). Field names are preserved in
**snake_case** to exactly match the API JSON.

## Environment variables

| Variable                   | Default                 | Description                      |
| -------------------------- | ----------------------- | -------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

Copy the example file and adjust as needed:

```bash
cp .env.example .env.local
```

## Setup & scripts

```bash
npm install          # install dependencies
npm run dev          # start dev server at http://localhost:3000
npm run build        # production build
npm run start        # serve the production build
npm run lint         # ESLint
npm run typecheck    # tsc --noEmit
npm run format       # Prettier (write)
npm run format:check # Prettier (check only)
```

The dashboard works even when the backend is offline: every view degrades
gracefully to a clear "API unavailable" message.
