AI Trading System — ARCHITECTURE.md
1. System Type

This is a modular event-driven quantitative trading platform.

It is NOT:

A monolithic bot
A real-time HFT system
A manual dashboard tool

It IS:

A distributed pipeline of independent services
Event + schedule driven
Built around data ingestion → transformation → decision → execution
2. High-Level Architecture
                ┌────────────────────────────┐
                │     External Market APIs    │
                │ IBKR | Finnhub | SEC | etc │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │   Ingestion Layer (FastAPI)│
                │  - collectors              │
                │  - normalizers             │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │   Firestore (Raw Data)     │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Feature Engineering Layer   │
                │  - indicators              │
                │  - aggregation             │
                │  - normalization           │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Catalyst Filter             │
                │ (events / news / filings)   │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Fundamental Engine          │
                │ - Quality Score (0–100)     │
                │ - quality_subscores         │
                │ - risk_flags                │
                │ (quality bias / FILTER)     │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Market Regime Engine        │
                │ - regime_state              │
                │ - risk_multiplier (0.5–1.5) │
                │ - exposure_recommendation   │
                │ (deterministic risk gate)   │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Signal Ranking Engine       │
                │ (LightGBM / scoring model)  │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ AI Reasoning Layer          │
                │ GPT-5 + RAG                 │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Risk Engine                 │
                │ - position sizing           │
                │ - exposure limits           │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Execution Engine (IBKR)     │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ Firestore (Trades + Logs)   │
                └────────────┬───────────────┘
                             │
                             v
                ┌────────────────────────────┐
                │ React UI (Next.js)          │
                └────────────────────────────┘
3. Core Services Breakdown
3.1 Ingestion Service

Responsibility:

Pull raw data from APIs
Normalize schema
Store in Firestore

Sources:

IBKR (prices, execution data)
Finnhub (news, fundamentals)
SEC EDGAR (filings)
Optional: options flow APIs

Runs:

Scheduled (GitHub Actions or Cloud Scheduler)
Event-triggered (news spike, earnings event)
3.2 Feature Engine

Responsibility:
Convert raw market data into structured signals:

Technical features
RSI
MACD
Moving averages
ATR
Bollinger bands
Market structure
Relative volume
Volatility expansion
Breakout detection
Trend strength
Cross-asset signals
Sector strength
Index correlation
Beta-adjusted movement

Output:

features/feature_{ticker}_{date}

Feature snapshots are top-level Firestore documents, not nested ticker/timestamp subcollections. This matches the database indexing strategy and keeps backtests simple to replay.
3.2.1 Fundamental Engine (NEW — additive)

Pipeline position:
Runs AFTER the Catalyst Filter (TRADING_ENGINE Stage 4) and BEFORE the Signal Ranking Engine (the scoring stage). Purely additive — it does not replace or rename any existing stage.

Purpose:
Evaluate long-term financial health and produce a Quality Score (0–100). This is NOT a long-term investing decision engine. It acts as a quality FILTER / bias that nudges short-term swing-trading candidates toward financially healthy names and away from fragile ones.

Inputs:

Financial statements (revenue, earnings, cashflow)
Balance-sheet metrics
Debt / leverage levels
Profitability metrics
Dilution / share-issuance trends

Outputs:

fundamental_score: 0–100
quality_subscores: { profitability_score, growth_score, leverage_score, cashflow_score }
risk_flags: e.g. bankruptcy_risk, dilution_risk

Authority:
Filter/bias only. It never places trades and never overrides the Risk Engine.
3.2.2 Market Regime Engine (NEW — additive)

Pipeline position:
Runs AFTER the Fundamental Engine and BEFORE the Signal Ranking Engine. Purely additive.

Purpose:
Detect the macro market environment and adjust risk appetite dynamically. It can REDUCE trading activity (throttle exposure / sizing) but NEVER places trades and NEVER overrides the deterministic Risk Engine.

Inputs:

SPY trend
VIX (volatility index)
Sector breadth
Market momentum
Cross-stock correlation

Outputs:

regime_state: bullish | neutral | bearish | high_volatility
risk_multiplier: 0.5–1.5
exposure_recommendation: low | medium | high

Authority:
Deterministic, hard risk constraint. The risk_multiplier and exposure_recommendation are applied deterministically downstream (see TRADING_ENGINE). AI may read regime_state for context but can NEVER override it.
3.3 Signal Ranking Engine

Purpose:
Reduce universe from ~6000 stocks → top candidates

Approach:

Gradient boosting model (LightGBM recommended)
Trained on historical trades
Output: probability of positive return over N days

Output:

signal_score: 0–100
expected_return: float
risk_score: float
3.4 AI Reasoning Layer

Purpose:
Interpret why something is moving

Inputs:

News articles
SEC filings
Earnings transcripts
Feature vector summary

Model:

GPT-5 (primary)
Optional smaller model pre-filter

Outputs:

- catalyst_type
- sentiment
- explanation
- risk_factors
- confidence_adjustment
- catalyst_direction: bullish | neutral | bearish
- ai_bias: -1.0 to +1.0

IMPORTANT:
AI does NOT decide trades alone.
AI never outputs trade direction as authority.

3.5 Risk Engine

This is a HARD RULE layer.

Rules:

Max portfolio exposure (e.g. 50–80%)
Max per trade risk (e.g. 1–2%)
Sector concentration limits
Volatility adjustment
Stop-loss logic

Example:

position_size =
    base_risk
    × confidence_score
    × volatility_scaler
3.6 Execution Engine

Connects to IBKR API.

Responsibilities:

Place orders
Modify orders
Cancel orders
Track fills
Sync portfolio state

Must be:

Idempotent
Retry-safe
Logged completely
3.7 Learning Layer (Critical)

Stores:

Entry features
AI reasoning output
Outcome after exit
Market conditions snapshot

Used for:

Backtesting
Model retraining
Feature selection
4. Data Flow Model
4.1 Daily Flow
Market Open

↓

Ingest price + news

↓

Compute features

↓

Catalyst filter

↓

Fundamental Engine (quality_score + risk_flags)

↓

Market Regime Engine (regime_state + risk_multiplier)

↓

Score all stocks (quality-biased)

↓

Select top candidates

↓

AI analysis on candidates

↓

Risk engine approval

↓

Execute trades

↓

Monitor positions

↓

Exit logic triggers

↓

Store results
4.2 Event Flow (Real-Time)

Triggers:

Earnings release
News spike
Volume anomaly

Flow:

Event detected

↓

Pull affected tickers

↓

Recompute features

↓

Re-score

↓

AI analysis

↓

Optional trade adjustment
5. Firestore Architecture (System-Level)
Root Collections
stocks/
features/
fundamentals/
market_regime/
signals/
trades/
positions/
news/
earnings/
insiders/
options_flow/
portfolios/
users/
logs/
jobs/
backtests/
ai_analysis/
6. Service Communication Pattern

No direct service-to-service coupling.

All communication is via:

Firestore (primary state store)
Redis (temporary cache / queues)
HTTP (FastAPI endpoints)
7. Scheduling Model

GitHub Actions + optional scheduler:

Jobs:
market_ingestion_job
feature_engine_job
fundamental_engine_job
market_regime_job
scoring_job
ai_analysis_job
execution_job
cleanup_job
backtest_job

Each job:

Stateless
Retry-safe
Logs to Firestore
8. Failure Handling Strategy

Every service must support:

Retry with exponential backoff
Idempotent writes
Partial failure recovery
Job resumption

Example:

If AI layer fails:

Phase 1 quant-only signals may still be generated.
Phase 3+ execution is blocked safely until ai_analysis_id exists.
9. Security Model
API keys stored in Firebase Secret Manager
IBKR credentials never stored in code
Role-based access for UI
Execution engine isolated from UI
10. Scalability Strategy

System designed for:

Phase 1:

Single VM / local server

Phase 2:

Multiple workers (Cloud Run / Kubernetes optional)

Phase 3:

Distributed ingestion + ML training pipeline
11. Design Philosophy
Data-first architecture
AI is a layer, not a controller
Deterministic systems must always override probabilistic ones
Every decision must be traceable