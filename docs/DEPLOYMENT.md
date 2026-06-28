AI Trading System — DEPLOYMENT.md
1. Purpose

This document defines the full deployment, CI/CD, and runtime infrastructure for the AI Trading System.

It ensures:

Fully automated deployments
Reproducible environments
Safe production execution
Separation of dev / staging / prod
Continuous backtesting + execution jobs
2. Environments

We define 3 environments:

2.1 Development
Local machine or dev VM
Firestore emulator (optional)
Paper trading only
Mock AI calls allowed
2.2 Staging
Firebase staging project
Real market data
Paper trading (IBKR paper account)
Full pipeline enabled
2.3 Production
Firebase production project
Live IBKR account
Strict risk controls enabled
AI + quant pipeline active
3. System Components Deployment
3.1 Frontend (Next.js UI)

Deployed via:

Firebase Hosting

Build process:

npm install
npm run build
firebase deploy

Environment variables:

FIREBASE_API_KEY
FIREBASE_PROJECT_ID
API_BASE_URL
3.2 Backend (Python FastAPI)

Deployment options:

Option A (Recommended Phase 1)
Single VPS (Hetzner / DigitalOcean)
Option B (Scalable)
Docker containers on Cloud Run or Kubernetes

Backend services:

ingestion_service
feature_engine
signal_engine
ai_pipeline
execution_engine
risk_engine
3.3 Database

Firestore:

Automatically managed via Firebase
Indexes defined in firestore.indexes.json

No manual DB server required.

4. GitHub Actions CI/CD

We use GitHub Actions as the orchestration layer.

4.1 Pipeline Overview
Push to main branch
        ↓
Run lint (ruff)
        ↓
Run tests (pytest)
        ↓
Build backend Docker image
        ↓
Deploy backend (VPS / Cloud Run)
        ↓
Deploy frontend (Firebase Hosting)
        ↓
Trigger ingestion job
        ↓
Run smoke tests
5. GitHub Actions Workflows
5.1 Backend CI

.github/workflows/backend.yml

Steps:

Install Python dependencies
Run linting (ruff + black)
Run unit tests
Build Docker image
Push image (optional registry)
5.2 Frontend CI

.github/workflows/frontend.yml

Steps:

Install Node dependencies
Run lint
Build Next.js app
Deploy to Firebase Hosting
5.3 Scheduled Jobs

.github/workflows/scheduler.yml

Runs on cron:

*/5 * * * *   → market ingestion
*/10 * * * *  → feature generation
*/15 * * * *  → signal scoring
*/30 * * * *  → AI pipeline
0 22 * * *    → daily backtest + learning job
6. Secrets Management

Stored in:

GitHub Secrets
Firebase Secret Manager
VPS environment variables
Required secrets:
IBKR_API_KEY
IBKR_ACCOUNT_ID
OPENAI_API_KEY
FINNHUB_API_KEY
FIREBASE_SERVICE_ACCOUNT
DATABASE_URL (if needed)
7. Backend Runtime Architecture
Process structure:
FastAPI Server
    ├── ingestion worker
    ├── feature worker
    ├── signal worker
    ├── AI worker
    ├── execution worker
    └── risk monitor

Each worker:

Stateless
Idempotent
Logs to Firestore
8. Job Execution Model

We use Fire-and-forget job pattern:

Example:

GitHub Action triggers job
        ↓
Writes job record to Firestore
        ↓
Backend worker picks it up
        ↓
Executes task
        ↓
Updates job status
9. Logging & Observability

All logs go to Firestore:

Collections:

logs/
jobs/
system_health/

Each log contains:

service name
severity
timestamp
message
metadata
10. Monitoring

Minimum monitoring layer:

Job success/failure tracking
API latency tracking
Trade execution logs
PnL tracking
AI cost tracking

Optional upgrades later:

Grafana dashboards
Prometheus metrics
Alerting (Slack/email)
11. Backtesting Deployment

Backtests run as scheduled jobs:

Triggered nightly
Uses historical Firestore + API data
Stores results in backtests/
12. Environment Configuration Strategy

Each environment has:

.env.dev
.env.staging
.env.prod

Never share production secrets with dev.

13. Safety Controls (Critical)

Production system includes hard safety checks:

Max daily loss limit
Max position exposure
Circuit breaker if AI behaves abnormally
Disable trading switch (kill switch)
14. Deployment Philosophy
Everything is automated
No manual production edits
Every change goes through GitHub
Full reproducibility required
15. Key Principle

If a trade cannot be reproduced from logs + data + code, it is considered invalid.