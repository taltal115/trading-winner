AI Trading System — DATABASE.md
1. Database Philosophy

This system uses Firestore as the single source of truth.

Design principles:

Human-readable IDs (NO hashes)
Time-series friendly structure
Append-only where possible
Every entity is traceable
Every trade is reconstructable
No hidden state

Firestore is used for:

Live system state
Historical data
AI training dataset
Audit trail
2. ID Naming Convention (IMPORTANT)

We avoid random IDs.

Format Rules
{entity}_{ticker}_{date}
{entity}_{ticker}_{timestamp}
{entity}_{id}

Examples:

signal_NVDA_2026-07-28
trade_NVDA_2026-07-28_093015
news_NVDA_2026-07-28_1
feature_NVDA_2026-07-28

Benefits:

Debuggable
Queryable
Human-readable
Backtest-friendly
3. Top-Level Collections
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
ai_analysis/
portfolios/
users/
backtests/
jobs/
logs/
market_snapshots/
models/
4. Collection Schemas
4.1 stocks/

Represents static metadata.

{
  "ticker": "NVDA",
  "name": "NVIDIA Corporation",
  "sector": "Technology",
  "industry": "Semiconductors",
  "marketCap": 2.3e12,
  "exchange": "NASDAQ",
  "currency": "USD",
  "active": true,
  "lastUpdated": "2026-07-28T10:00:00Z"
}
4.2 features/

Time-series engineered features.

Document ID:

feature_NVDA_2026-07-28

Path:

features/feature_NVDA_2026-07-28

Do NOT use nested paths such as features/{ticker}/{timestamp}. Feature snapshots are top-level documents to preserve simple indexing, easier backtesting, and consistent traceability.
{
  "ticker": "NVDA",
  "timestamp": "2026-07-28T10:00:00Z",

  "technical": {
    "rsi": 62.3,
    "macd": 1.12,
    "atr": 4.5,
    "sma_20": 890.2,
    "sma_50": 870.1
  },

  "volume": {
    "relativeVolume": 2.4,
    "avgVolume": 45000000
  },

  "momentum": {
    "dailyReturn": 0.034,
    "weeklyReturn": 0.12,
    "monthlyReturn": 0.31
  },

  "volatility": {
    "stdDev": 0.018,
    "bollingerWidth": 0.09
  }
}
4.2.1 fundamentals/ (NEW — additive)

Per-ticker, per-date snapshot of the Fundamental Engine output (Quality Score + subscores + risk flags).

Document ID:

fundamental_NVDA_2026-07-28

Path:

fundamentals/fundamental_NVDA_2026-07-28

ID format justification:
Follows the established {entity}_{ticker}_{date} convention (identical shape to feature_NVDA_2026-07-28). Snapshots are top-level documents (no nested paths) to preserve simple indexing, easy backtest replay, and consistent traceability. Human-readable, no hashes.

{
  "ticker": "NVDA",
  "date": "2026-07-28",
  "timestamp": "2026-07-28T10:00:00Z",

  "fundamental_score": 78,

  "quality_subscores": {
    "profitability_score": 84,
    "growth_score": 81,
    "leverage_score": 66,
    "cashflow_score": 80
  },

  "risk_flags": [
    "dilution_risk"
  ],

  "inputs_summary": {
    "revenue_ttm": 1.15e11,
    "earnings_ttm": 5.6e10,
    "operating_cashflow_ttm": 6.4e10,
    "total_debt": 1.0e10,
    "debt_to_equity": 0.21,
    "shares_outstanding_trend": "rising"
  },

  "source": "finnhub",
  "engineVersion": "fundamental-v1"
}

Notes:
- fundamental_score is 0–100. quality_subscores fields are each 0–100.
- risk_flags is an enumerated list, e.g. bankruptcy_risk, dilution_risk.
4.2.2 market_regime/ (NEW — additive)

Market-wide (NOT per-ticker), one document per cycle/date. Stores the Market Regime Engine output used as a deterministic risk constraint.

Document ID:

regime_2026-07-28

Path:

market_regime/regime_2026-07-28

ID format justification:
Regime is a macro, market-level entity not tied to any single ticker, so the per-ticker form does not apply. We use the {entity}_{id} convention with the date as the id (regime_{date}), mirroring the human-readable, hash-free style of the other collections and keeping it append-only and backtest-friendly. For intraday recomputes, the {entity}_{timestamp} form (regime_2026-07-28_1330) may be used, consistent with existing timestamped-id rules.

{
  "date": "2026-07-28",
  "timestamp": "2026-07-28T10:00:00Z",

  "regime_state": "neutral",

  "risk_multiplier": 1.0,

  "exposure_recommendation": "medium",

  "inputs_summary": {
    "spy_trend": "up",
    "vix": 16.4,
    "sector_breadth": 0.58,
    "market_momentum": 0.21,
    "cross_stock_correlation": 0.42
  },

  "engineVersion": "market-regime-v1"
}

Notes:
- regime_state ∈ { bullish, neutral, bearish, high_volatility }.
- risk_multiplier ∈ [0.5, 1.5]. exposure_recommendation ∈ { low, medium, high }.
4.3 signals/

Core trading decisions.

Document ID:

signal_NVDA_2026-07-28
{
  "ticker": "NVDA",
  "timestamp": "2026-07-28T10:05:00Z",

  "score": 87,
  "expectedReturn": 0.042,
  "riskScore": 0.23,

  "strategy": "momentum_catalyst",

  "feature_snapshot_id": "feature_NVDA_2026-07-28",

  "aiConfidence": 0.78,

  "aiSummary": "Strong AI infrastructure demand + breakout momentum",

  "decision": "APPROVED",

  "status": "OPEN"
}
4.4 trades/

Execution records.

Document ID:

trade_NVDA_2026-07-28_093015
{
  "ticker": "NVDA",

  "entryTime": "2026-07-28T09:30:15Z",
  "exitTime": null,

  "entryPrice": 892.5,
  "exitPrice": null,

  "quantity": 10,

  "side": "LONG",

  "status": "OPEN",

  "signal_id": "signal_NVDA_2026-07-28",

  "feature_snapshot_id": "feature_NVDA_2026-07-28",

  "ai_analysis_id": null,

  "pnl": null,

  "fees": 1.2
}

Execution dependency rule:

Phase 1:
- ai_analysis_id may be null for quant-only signal generation and paper/watch workflows.

Phase 3+:
- ai_analysis_id is required before trade execution.

All phases:
- signal_id and feature_snapshot_id are required.
4.5 positions/

Real-time portfolio state.

{
  "ticker": "NVDA",
  "quantity": 10,
  "avgEntryPrice": 892.5,

  "marketValue": 9100,
  "unrealizedPnL": 175,

  "riskExposure": 0.12,

  "openedAt": "2026-07-28T09:30:15Z"
}
4.6 news/
{
  "ticker": "NVDA",
  "timestamp": "2026-07-28T08:45:00Z",

  "headline": "NVIDIA announces new AI chip partnership",
  "source": "Reuters",

  "sentiment": "positive",

  "relevanceScore": 0.93,

  "rawText": "...",

  "embeddingId": "emb_news_123"
}
4.7 earnings/
{
  "ticker": "NVDA",
  "quarter": "Q2-2026",

  "epsActual": 5.12,
  "epsExpected": 4.8,

  "surprise": 0.32,

  "guidance": "raised",

  "reaction": "bullish"
}
4.8 ai_analysis/

Stores LLM reasoning outputs.

{
  "relatedId": "signal_NVDA_2026-07-28",

  "ticker": "NVDA",

  "summary": "AI demand accelerating due to hyperscaler capex",

  "catalysts": [
    "AI infrastructure demand",
    "New chip cycle"
  ],

  "risks": [
    "Valuation stretched",
    "Macro sensitivity"
  ],

  "confidence": 0.82,

  "catalyst_direction": "bullish",

  "ai_bias": 0.18,

  "reasoningVersion": "gpt-5-v1"
}
4.9 backtests/

Stores strategy evaluation results.

{
  "strategy": "momentum_catalyst_v1",

  "startDate": "2024-01-01",
  "endDate": "2025-12-31",

  "metrics": {
    "sharpe": 1.42,
    "winRate": 0.53,
    "maxDrawdown": 0.18,
    "totalReturn": 0.67
  }
}
4.10 logs/

System-wide logs.

{
  "service": "signal_engine",
  "level": "INFO",

  "message": "Signal generated for NVDA",

  "timestamp": "2026-07-28T10:05:00Z"
}
5. Query Patterns
Get top signals
signals where status == OPEN order by score desc limit 20
Get trade history
trades where ticker == NVDA order by entryTime desc
Get full learning cycle
signal → ai_analysis → trade → outcome
6. Time-Series Strategy

We never overwrite historical data.

We always:

Append new signals
Append features per timestamp
Append trades
Append AI reasoning

This enables:

full reconstruction of market state at any moment

7. Indexing Strategy

Required indexes:

signals(score, timestamp)
trades(ticker, entryTime)
news(ticker, timestamp)
features(ticker, timestamp)
fundamentals(ticker, date)
market_regime(date)
8. Data Integrity Rules
Every trade must reference signal_id
Every trade must reference feature_snapshot_id
Every Phase 3+ executed trade must reference ai_analysis_id
Every signal must reference a feature snapshot
Every AI analysis must reference a signal or trade
No orphan records allowed
8.1 Traceability for new engines (NEW — additive, backward compatible)
Every signal SHOULD reference fundamental_id (e.g. fundamental_NVDA_2026-07-28) when a fundamentals snapshot exists for the ticker/date — this makes the applied QualityBias reconstructable.
Every signal SHOULD reference market_regime_id (e.g. regime_2026-07-28) — the regime document whose risk_multiplier/exposure_recommendation governed its sizing/exposure.
These references are additive: optional in Phase 1 (no breaking change to the existing signals schema), recommended from the phase where the engines are live, so the full chain feature → fundamental → regime → signal → ai_analysis → trade → outcome remains replayable.
fundamentals/ and market_regime/ documents are append-only and reachable via {ticker}_{date} or {date}; no orphan records allowed.
9. Learning Dataset Structure

Final ML dataset is derived from:

features + signals + news + outcomes

Label:

future return after N days
10. Design Philosophy
Firestore is not just storage — it's the system memory
Every decision must be replayable
Every prediction must be auditable
No hidden computations