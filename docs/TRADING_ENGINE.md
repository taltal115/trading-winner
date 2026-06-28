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