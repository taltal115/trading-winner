/**
 * TypeScript types mirroring the backend pydantic models.
 *
 * Field names are kept in snake_case to exactly match the FastAPI JSON
 * responses (backend/app/models/entities.py, ai.py). Do NOT rename to
 * camelCase — the API is snake_case everywhere.
 */

// --- Enums (backend/app/models/enums.py) ---

export type TradeSide = "LONG" | "SHORT";

export type TradeStatus = "OPEN" | "CLOSED" | "CANCELLED";

export type SignalDecision = "STRONG_BUY" | "BUY" | "WATCH" | "IGNORE";

export type SignalStatus = "OPEN" | "CLOSED";

export type CatalystDirection = "bullish" | "neutral" | "bearish";

export type CatalystType =
  "earnings" | "news" | "macro" | "insider" | "unknown";

export type Sentiment = "positive" | "neutral" | "negative";

// --- Signals (GET /signals, GET /signals/{id}) ---

export interface ScoreBreakdown {
  momentum_score: number;
  volume_score: number;
  catalyst_score: number;
  sector_strength: number;
  volatility_breakout: number;
  macro_alignment: number;
}

export interface Signal {
  id: string;
  ticker: string;
  timestamp: string;
  score: number;
  score_breakdown: ScoreBreakdown;
  expected_return: number;
  risk_score: number;
  strategy: string;
  feature_snapshot_id: string;
  ai_analysis_id: string | null;
  decision: SignalDecision;
  status: SignalStatus;
}

// --- AI Analyses (GET /ai, GET /ai/{id}) ---

export interface AiAnalysis {
  id: string;
  related_id: string;
  ticker: string;
  summary: string;
  catalyst_type: CatalystType;
  catalyst_direction: CatalystDirection;
  ai_bias: number;
  sentiment: Sentiment;
  key_insights: string[];
  risk_factors: string[];
  confidence: number;
  confidence_adjustment: number;
  reasoning_version: string;
  prompt_version: string;
  embedding_version: string;
}

// --- Portfolio, Positions, Trades ---

/** GET /portfolio — a derived summary object, not the raw Portfolio entity. */
export interface PortfolioSummary {
  equity: number;
  cash: number;
  open_positions: number;
  exposure: number;
  updated_at: string;
}

/** GET /positions — Position entity (backend/app/models/entities.py). */
export interface Position {
  id: string;
  ticker: string;
  sector: string;
  quantity: number;
  avg_entry_price: number;
  market_value: number;
  unrealized_pnl: number;
  risk_exposure: number;
  stop_price: number;
  target_price: number;
  opened_at: string;
  trade_id: string;
}

/** GET /trades — Trade entity. */
export interface Trade {
  id: string;
  ticker: string;
  side: TradeSide;
  entry_time: string;
  exit_time: string | null;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  status: TradeStatus;
  signal_id: string;
  feature_snapshot_id: string;
  ai_analysis_id: string | null;
  risk_decision_id: string | null;
  pnl: number | null;
  fees: number;
}

// --- Position reconciliation (GET /positions/reconcile) ---

export interface PositionDiscrepancy {
  ticker: string;
  kind: "quantity_mismatch" | "missing_at_broker" | "untracked_internally";
  internal_quantity: number;
  broker_quantity: number;
}

export interface ReconciliationReport {
  in_sync: boolean;
  matched: string[];
  discrepancies: PositionDiscrepancy[];
}

// --- Backtests (GET /backtests, GET /backtests/{id}) ---

export interface BacktestMetrics {
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  total_return: number;
}

export interface Backtest {
  id: string;
  strategy: string;
  start_date: string;
  end_date: string;
  tickers: string[];
  trade_count: number;
  metrics: BacktestMetrics;
  created_at: string;
}

// --- System / health / trading status ---

export interface HealthStatus {
  status: string;
  environment: string;
  phase: number;
}

export interface IntegrityReport {
  ok: boolean;
  violations: string[];
}

/** GET /trading/status — display only; UI never triggers halt/resume. */
export interface TradingStatus {
  halted: boolean;
  reasons: string[];
  kill_switch_enabled: boolean;
  halt_reason: string | null;
}
