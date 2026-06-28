AI Trading System — TRADING_ENGINE.md
1. Purpose

The Trading Engine is responsible for:

Scanning the full stock universe
Filtering candidates
Scoring opportunities
Enforcing risk rules
Generating trade decisions
Maintaining PDT-safe swing trading behavior

It is the final deterministic authority before execution.

2. Core Philosophy
2.1 No emotional logic

No discretionary decisions.

Everything must be:

Quantifiable
Reproducible
Backtestable
2.2 AI cannot override risk rules

AI may:

Suggest
Explain
Enhance signals
Describe catalyst direction
Provide bounded bias

AI may NOT:

Force trades
Override risk engine
Output trade direction as authority
2.3 Multi-stage filtering

We never evaluate all stocks with AI.

We reduce universe step-by-step:

6000 stocks
→ 200 liquid candidates
→ 50 momentum/catalyst candidates
→ 10 AI-reviewed candidates
→ 1–5 trades executed
3. System Pipeline
Stage 1: Universe Filter

Filters all US equities.

Rules:

Market cap > 1B
Avg volume > 1M
Price > $5
Active trading status

Output:
~200–800 stocks

Stage 2: Liquidity & Volatility Filter

We remove dead or flat stocks.

Conditions:

Relative volume > 1.5
ATR > threshold
Daily volatility > minimum

Output:
~100–200 stocks

Stage 3: Momentum Filter

We identify trending stocks.

Signals:

Price above 20 SMA
20 SMA above 50 SMA
50 SMA above 200 SMA
5-day return > sector median

Output:
~30–80 stocks

Stage 4: Catalyst Filter

We check for events:

Earnings (past 7 days or upcoming)
News spike (>2 articles/hour)
SEC filings (8-K)
Insider activity
Unusual options flow

Output:
~10–30 stocks

Stage 4.5: Fundamental Engine (NEW — additive)

Runs AFTER the Catalyst Filter and BEFORE the Scoring Engine. It does not remove or rename any stage; it only adds a quality bias/filter.

Purpose:
Produce a Quality Score (0–100) reflecting long-term financial health, used as a short-term swing-trading quality bias. NOT a long-term investing decision engine.

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

Hard filter (deterministic):
If risk_flags contains bankruptcy_risk, OR fundamental_score < 20 → candidate is downgraded to IGNORE regardless of any other score or AI input.

Output (unfiltered candidates pass through to scoring):
~10–30 stocks (same set, now annotated with fundamental_score)

Stage 4.6: Market Regime Engine (NEW — additive)

Runs AFTER the Fundamental Engine and BEFORE the Scoring Engine. It is market-wide (not per-ticker) and computed once per cycle.

Purpose:
Detect the macro environment and set a deterministic risk appetite. It can REDUCE activity (throttle sizing / exposure) but NEVER places trades and NEVER overrides the Risk Engine.

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

This risk_multiplier is a deterministic, hard constraint applied to sizing/exposure (see sections 6 and 7). AI cannot override it.

Stage 5: Scoring Engine

We compute final score:

4. Scoring Model
FinalScore =

(0.30 × MomentumScore)
+ (0.20 × VolumeScore)
+ (0.20 × CatalystScore)
+ (0.15 × SectorStrength)
+ (0.10 × VolatilityBreakout)
+ (0.05 × MacroAlignment)

Each score is normalized 0–100.

4.1 MomentumScore

Based on:

5D return
20D return
relative strength vs SPY
4.2 CatalystScore

Based on:

News sentiment
Earnings surprise
SEC filings
Options flow
4.3 VolumeScore
Relative volume
Breakout volume spike
Institutional activity proxy
4.4 Fundamental Quality Bias (NEW — additive)

The Fundamental Engine's fundamental_score is applied as a bounded quality bias/filter, NOT as a new weighted alpha term. This preserves the existing six weights (0.30/0.20/0.20/0.15/0.10/0.05) and keeps backtests of the base formula reproducible (backward compatible).

QualityBias =
0.9 + 0.2 × (fundamental_score / 100)

This bounds the bias to the range [0.9, 1.1] — at most ±10%. High-quality names get a mild boost; low-quality names get a mild penalty.

Before (unchanged base score):

FinalScore =
(0.30 × MomentumScore)
+ (0.20 × VolumeScore)
+ (0.20 × CatalystScore)
+ (0.15 × SectorStrength)
+ (0.10 × VolatilityBreakout)
+ (0.05 × MacroAlignment)

After (quality-biased score):

QualityBiasedScore =
FinalScore × QualityBias

Hard fundamental filter (deterministic, see Stage 4.5):
If risk_flags contains bankruptcy_risk OR fundamental_score < 20 → decision is forced to IGNORE, regardless of QualityBiasedScore or AI output.
5. AI Enhancement Layer

AI is applied ONLY after scoring.

Input to AI:
Top 10 signals
News articles
Feature summary
Catalyst context
Output:
{
  "summary": "...",
  "catalystType": "earnings | news | macro | unknown",
  "riskFlags": ["overextended", "low conviction"],
  "confidenceAdjustment": -0.12,
  "explanation": "..."
}
6. Final Decision Engine

We compute:

AdjustedScore =
FinalScore × (1 + AI_Adjustment)

Decision rules:

85 → STRONG BUY

70–85 → BUY
50–70 → WATCH
< 50 → IGNORE
6.1 Updated Decision Chain (NEW — additive)

The decision chain is extended additively to incorporate the Fundamental quality bias (Stage 4.5 / §4.4) and the Market Regime risk_multiplier (Stage 4.6). The decision thresholds above are UNCHANGED.

Before (base chain):

AdjustedScore =
FinalScore × (1 + AI_Adjustment)
→ thresholds applied to AdjustedScore

After (quality + regime aware chain):

QualityBiasedScore =
FinalScore × QualityBias            (deterministic, from §4.4)

AdjustedScore =
QualityBiasedScore × (1 + AI_Adjustment)   (AI enrichment, bounded)

→ thresholds (85 / 70–85 / 50–70 / <50) applied to AdjustedScore, unchanged.

Deterministic ordering (must hold):
1. QualityBias and the hard fundamental filter are deterministic and applied BEFORE AI.
2. AI_Adjustment is bounded enrichment applied to the quality-biased score.
3. The Market Regime risk_multiplier and exposure_recommendation are applied AFTER AI, deterministically, to sizing and exposure (§7 and §11). AI has no input into and CANNOT override the regime layer.
4. The hard fundamental filter (bankruptcy_risk / fundamental_score < 20) forces IGNORE regardless of AdjustedScore or AI output.
7. Position Sizing Model

We do NOT use fixed size trades.

We use risk-based sizing:

PositionSize =

(AccountEquity × RiskPerTrade × ConfidenceMultiplier)
/ StopDistance
Defaults:
RiskPerTrade = 1% of equity
ConfidenceMultiplier = 0.5 → 1.5
StopDistance = ATR-based (e.g. 2 × ATR)
7.1 Regime-Adjusted Sizing (NEW — additive)

The Market Regime risk_multiplier (0.5–1.5) is applied to position sizing as a deterministic, hard constraint. This is where the regime layer throttles or expands activity.

Before (base sizing):

PositionSize =
(AccountEquity × RiskPerTrade × ConfidenceMultiplier)
/ StopDistance

After (regime-adjusted sizing):

PositionSize =
(AccountEquity × RiskPerTrade × ConfidenceMultiplier × RiskMultiplier)
/ StopDistance

Where RiskMultiplier = market_regime.risk_multiplier (0.5–1.5).

Additionally, exposure_recommendation deterministically caps new activity:
- low → reduce max open positions and total exposure (e.g. defensive throttle), bias toward no new entries.
- medium → standard limits (§11).
- high → standard limits; never exceeds the hard caps in §11.

The regime layer can only REDUCE risk below or scale it within the §11 hard limits — it never relaxes a hard cap, never places trades, and AI cannot override it.
8. Exit Strategy

We use hybrid exit logic:

8.1 Time-based exit
Max hold: 10 trading days
8.2 Profit taking
+8% → partial exit
+12–15% → full exit (unless strong trend)
8.3 Stop loss
-2 ATR or -5% (whichever smaller)
8.4 Momentum failure

Exit if:

SMA trend breaks
Relative strength drops below sector
9. PDT Compliance Layer

To avoid PDT violation:

System enforces:

No more than 3 intraday round trips/week
Minimum holding period: 24 hours
Preference for swing trades (2–10 days)

If violation risk detected:

BLOCK TRADE
or convert to swing-only mode
10. Execution Rules

Before sending order:

Validate risk limits
Check portfolio exposure
Confirm liquidity
Confirm no duplicate positions
Confirm signal_id exists
Confirm feature_snapshot_id exists
Confirm ai_analysis_id exists in Phase 3+

Execution types:

Market order (default)
Limit order (for volatility spikes)
11. Portfolio Constraints

Hard limits:

Max 10–15 open positions
Max sector exposure: 25%
Max single position: 10% equity
Cash buffer minimum: 10%
12. Rebalancing Logic

Daily:

Re-score open positions
Exit weakest signals
Add stronger signals
13. Learning Hooks

Every decision logs:

Feature snapshot
Score breakdown
AI reasoning
Final decision
Outcome after exit

Used for:

Model retraining
Strategy tuning
Feature importance analysis
14. System Output

Trading Engine produces:

signals/
trades/
risk_decisions/
position_updates/
15. Design Philosophy
Deterministic first
AI second
Execution last
Learning always