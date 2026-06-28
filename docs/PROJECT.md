AI Trading System — PROJECT.md
1. Vision

This project is a modular, event-driven AI-assisted quantitative trading system designed for swing trading (2–10 day holding period), avoiding PDT restrictions and high-frequency complexity.

The system combines:

Rule-based quantitative filters
Market data ingestion
News + catalyst detection
AI reasoning layer (LLMs)
Risk-managed execution engine
Continuous learning loop from trades

The goal is not manual trading assistance, but a semi-autonomous trading intelligence system that:

Discovers opportunities across US equities
Scores them probabilistically
Executes trades via broker API under strict risk rules
Learns from outcomes over time

This system is designed for:

Individual developer deployment
Low-to-mid infrastructure cost (< $100–300/month initial target)
Extensible to institutional-grade architecture
2. Core Principles
2.1 No Single Indicator Strategy

No standalone indicator (RSI, MACD, moving average) is considered predictive enough.

All decisions are:

multi-factor probabilistic scoring models

2.2 AI is NOT the strategy

LLMs are used for:

News interpretation
Catalyst detection
Risk explanation
Feature enrichment

NOT for:

Direct buy/sell decisions without quantitative filtering
2.3 Deterministic First, AI Second

Pipeline rule:

Deterministic filters reduce universe
Statistical scoring ranks candidates
AI enriches top candidates only
Execution engine enforces risk rules
2.4 Event-Driven Trading

The system reacts to:

Earnings releases
News spikes
Unusual volume
Options flow changes
Insider trades
Sector rotations
3. Target Strategy Type

Primary strategy class:

Swing trading (2–10 days)
Catalyst + momentum hybrid
High relative strength equities
Liquid US equities only

Avoid:

HFT / scalping
Intraday PDT-restricted trading
Illiquid small caps
4. System Outputs

The system continuously produces:

4.1 Signals
Ranked trade opportunities
Confidence score (0–100)
Expected return distribution
Risk score
4.2 Trades
Entry / exit orders
Position sizing
Stop logic
Time-based exits
4.3 Analytics
Strategy performance
Win rate, Sharpe, drawdown
Feature importance
AI reasoning logs
5. High-Level Architecture
                 +----------------------+
                 |   Market Data APIs   |
                 | (IBKR, Finnhub, etc) |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 |  Data Ingestion      |
                 | (FastAPI + Workers)  |
                 +----------+-----------+
                            |
                            v
        +--------------------------------------+
        |        Feature Engineering Layer     |
        |  - Technical indicators             |
        |  - Volume / volatility              |
        |  - Sector strength                  |
        |  - News signals                     |
        +------------------+-------------------+
                           |
                           v
        +--------------------------------------+
        |     Quant Ranking Engine             |
        |  (LightGBM / scoring model)         |
        +------------------+-------------------+
                           |
                           v
        +--------------------------------------+
        |        AI Reasoning Layer            |
        |  - News interpretation              |
        |  - Catalyst detection               |
        |  - Risk explanation                 |
        +------------------+-------------------+
                           |
                           v
        +--------------------------------------+
        |      Risk Management Engine          |
        |  - Position sizing                  |
        |  - Exposure limits                  |
        |  - Portfolio constraints            |
        +------------------+-------------------+
                           |
                           v
        +--------------------------------------+
        |       Execution Engine (IBKR)        |
        +--------------------------------------+
                           |
                           v
                 +----------------------+
                 |   Firestore DB       |
                 +----------------------+
                           |
                           v
                 +----------------------+
                 |   React UI (TV-like) |
                 +----------------------+
6. Technology Stack
Backend
Python 3.13
FastAPI
Pydantic v2
Polars (preferred over Pandas for performance)
LightGBM / XGBoost
Scikit-learn
Redis (queue/cache)
APScheduler / Celery workers
Market Data
Interactive Brokers API (execution + data)
Finnhub (news + fundamentals)
SEC EDGAR (filings)
Optional later: Polygon / Benzinga / Options flow APIs
AI Layer
OpenAI GPT-5 (or equivalent frontier model)
Embeddings model for RAG
Small model optional for pre-filtering
Frontend
Next.js (React)
TypeScript
TailwindCSS
shadcn/ui
TradingView Lightweight Charts
Infrastructure
Firebase Hosting (frontend)
Firestore (database)
GitHub Actions (CI/CD + jobs)
Docker (backend services)
7. Key Constraints
7.1 PDT Compliance

System must:

Avoid day trading patterns
Hold positions > 24h minimum
Prefer 2–10 day holding periods
7.2 Cost Constraint (Phase 1)

Target:

<$100/month initial running cost
Use free tiers aggressively
AI usage strictly filtered
7.3 Latency Not Critical

This is NOT HFT.

Acceptable delays:

Minutes to hours
8. AI Usage Philosophy

AI is used only when:

Candidate already passed quantitative filters
Event or catalyst is present
Human-level reasoning is required

AI outputs:

News interpretation
Catalyst classification
Risk explanation
Confidence adjustment
Trade justification text

AI is NOT used for scanning full market universe.

9. Data Philosophy

All data is stored for:

Backtesting
Learning loop
Feature improvement

Every trade becomes a training sample.

10. Learning Loop (Critical)

Each trade produces:

Feature vector at entry time
AI reasoning output
Market state snapshot
Outcome after exit
Performance attribution

This enables:

continuous strategy improvement over time

11. Success Criteria

System is considered successful if:

Positive expectancy over 200+ trades
Stable drawdown (<15–20%)
Win rate > 45% (not required but ideal)
Sharpe > 1.2 (target range)
Fully automated signal generation pipeline works reliably
12. Future Extensions
Options trading module
Crypto module
Multi-strategy portfolio allocator
Reinforcement learning policy layer
Institutional data feeds
Multi-agent AI trading system
13. Development Philosophy
Build modular components
Avoid monolithic bot logic
Every module independently testable
Every decision logged
Everything reproducible