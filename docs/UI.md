AI Trading System — UI.md
1. Purpose

The UI is a real-time trading intelligence dashboard inspired by TradingView.

It is NOT:

A retail trading app
A manual trading interface

It IS:

A monitoring + decision visibility system
A signal inspection tool
A portfolio + risk dashboard
A research + backtest interface

Execution happens in backend systems.

2. Tech Stack
Frontend Framework
Next.js (App Router)
TypeScript
TailwindCSS
shadcn/ui
Zustand (light state management)
React Query (server state)
Charts
TradingView Lightweight Charts (core)
Optional: Recharts for analytics dashboards
Backend Integration
Firebase Firestore (real-time sync)
Firebase Auth
WebSockets (optional for live signals)
3. UI Design Philosophy
3.1 TradingView-inspired layout
Dark mode default
Minimal UI noise
High density of information
Fast scanning of signals
3.2 Priority of information
Signals (most important)
Open positions
Portfolio PnL
Market chart
News + catalysts
AI explanations
4. Application Layout
┌──────────────────────────────────────────────┐
│ Top Bar: PnL | Exposure | Cash | Alerts     │
├───────────────┬──────────────────────────────┤
│ Watchlist     │ Main Chart (TradingView)    │
│ Signals       │                              │
│ Positions     │                              │
│ News Feed     │                              │
│ AI Insights   │                              │
├───────────────┴──────────────────────────────┤
│ Signal Detail Panel (expandable)             │
└──────────────────────────────────────────────┘
5. Pages Structure
5.1 Dashboard (/)

Main overview:

Market status
Market Regime widget (read-only — NEW)
Top signals
Portfolio summary
Active trades
5.2 Signals (/signals)

Displays:

Ranked opportunities
Score breakdown
Fundamental Score breakdown (subscores + risk_flags, read-only — NEW)
AI reasoning
Entry suggestions

Each signal card:

{
  "ticker": "NVDA",
  "score": 87,
  "expectedReturn": "4.2%",
  "risk": "low",
  "catalyst": "AI infrastructure demand",
  "confidence": 0.82
}
5.3 Chart View (/chart/[ticker])

Main TradingView-style chart:

Candlesticks
Volume
Indicators overlay
Event markers (news, earnings, signals)
5.4 Positions (/positions)
Open trades
PnL tracking
Entry price vs current price
Risk exposure
5.5 News (/news)
Real-time news feed
Filter by ticker
Sentiment labels
AI summaries
5.6 AI Insights (/ai)
AI reasoning logs
Catalyst explanations
Trade justification
Model confidence tracking
5.7 Backtests (/backtests)
Strategy performance
Equity curve
Sharpe ratio
Drawdown
Trade list
5.8 Settings (/settings)
API keys status
Risk limits
Strategy toggles
Model version selection
6. Core Components
6.1 Signal Card
┌──────────────────────────────┐
│ NVDA                        │
│ Score: 87                   │
│ Expected: +4.2%             │
│ Risk: Low                   │
│ Catalyst: AI demand surge   │
│ Confidence: 0.82            │
└──────────────────────────────┘
6.2 Trading Chart Component

Features:

Candlestick chart
Volume bars
Moving averages
Signal markers
News markers
6.3 Portfolio Widget
Total equity
Daily PnL
Exposure %
Cash available
Drawdown indicator
6.4 News Feed Item
[NVDA] NVIDIA announces AI chip expansion
Sentiment: Positive
Impact: High
6.5 AI Explanation Panel

Displays:

Summary
Catalyst type
Risk factors
Confidence score
Reasoning trace
6.6 Market Regime Widget (NEW — read-only)

Lives on the Dashboard. Subscribes to market_regime/ (latest regime_{date} document). Display only — it never computes regime or risk.

┌──────────────────────────────┐
│ Market Regime               │
│ State: NEUTRAL              │
│ Risk Multiplier: 1.0x       │
│ Exposure: MEDIUM            │
└──────────────────────────────┘

Fields shown:
regime_state (bullish | neutral | bearish | high_volatility)
risk_multiplier (0.5–1.5)
exposure_recommendation (low | medium | high)

Color cues (display only): bullish = green, neutral = gray, bearish = red, high_volatility = amber.
6.7 Fundamental Score Breakdown (NEW — read-only)

Lives on the Signal page / signal detail panel. Subscribes to fundamentals/ (fundamental_{ticker}_{date}). Display only — it never computes scores.

┌──────────────────────────────┐
│ Fundamental Quality: 78     │
│ Profitability: 84           │
│ Growth: 81                  │
│ Leverage: 66                │
│ Cashflow: 80                │
│ Risk Flags: dilution_risk   │
└──────────────────────────────┘

Fields shown:
fundamental_score (0–100)
quality_subscores: profitability_score, growth_score, leverage_score, cashflow_score
risk_flags (e.g. bankruptcy_risk, dilution_risk)
7. Real-Time Data Flow

Firestore subscriptions:

signals/
positions/
trades/
news/
market_snapshots/
fundamentals/
market_regime/

UI auto-updates via:

Firestore listeners
React Query cache updates
8. State Management
Zustand stores:
user settings
UI layout state
selected ticker
React Query:
server data
caching
background refresh
9. Firebase Integration
Authentication
Google login
Optional email/password
Hosting
Next.js deployed via Firebase Hosting
Firestore Usage
Real-time dashboard updates
Signal streaming
Portfolio sync
10. UX Rules
No clutter
No popups unless critical alerts
Everything must be scannable in <3 seconds
All critical signals visible without scrolling
11. Alerts System

Types:

New high-confidence signal
Position stop-loss hit
Earnings event detected
AI anomaly detection

Delivery:

UI toast
Optional email/webhook later
12. Performance Requirements
Initial load < 2 seconds
Chart rendering < 200ms update latency
Firestore updates reflected in < 1 second
13. Design Inspiration
TradingView (charts)
Bloomberg Terminal (density of info)
Robinhood (simplicity)
QuantConnect (data clarity)
14. Key Principle

The UI does NOT decide trades — it explains them.

Everything displayed is:

Traceable to data
Traceable to AI reasoning
Traceable to signals engine