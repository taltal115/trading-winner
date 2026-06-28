/**
 * Centralized, typed API client for the read-only trading dashboard.
 *
 * STRICTLY READ-ONLY: every helper issues an HTTP GET. There is intentionally
 * no POST/PUT/PATCH/DELETE support here. The UI must never mutate backend state
 * (no pipeline runs, no trading halt/resume, no position monitor triggers).
 *
 * The base URL comes from NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000).
 * Every call returns an ApiResult so pages can render friendly error/empty
 * states instead of crashing when the backend is unavailable in dev.
 */

import type {
  AiAnalysis,
  Backtest,
  HealthStatus,
  IntegrityReport,
  PortfolioSummary,
  Position,
  ReconciliationReport,
  Signal,
  TradingStatus,
  Trade,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export type ApiResult<T> =
  { ok: true; data: T } | { ok: false; error: string; status?: number };

/** Internal GET helper. Never cached: the dashboard reflects live backend state. */
async function get<T>(path: string): Promise<ApiResult<T>> {
  const url = `${API_BASE_URL}${path}`;
  try {
    const response = await fetch(url, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body?.detail) detail = body.detail;
      } catch {
        // response had no JSON body; keep the status-based message
      }
      return { ok: false, error: detail, status: response.status };
    }

    const data = (await response.json()) as T;
    return { ok: true, data };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown network error";
    return {
      ok: false,
      error: `API unavailable at ${API_BASE_URL} (${message})`,
    };
  }
}

export const api = {
  // System
  getHealth: () => get<HealthStatus>("/health"),
  getIntegrity: () => get<IntegrityReport>("/system/integrity"),
  getTradingStatus: () => get<TradingStatus>("/trading/status"),

  // Signals
  getSignals: (limit = 50) => get<Signal[]>(`/signals?limit=${limit}`),
  getSignal: (signalId: string) =>
    get<Signal>(`/signals/${encodeURIComponent(signalId)}`),

  // Portfolio / positions / trades
  getPortfolio: () => get<PortfolioSummary>("/portfolio"),
  getPositions: () => get<Position[]>("/positions"),
  getReconciliation: () => get<ReconciliationReport>("/positions/reconcile"),
  getTrades: () => get<Trade[]>("/trades"),

  // Backtests
  getBacktests: () => get<Backtest[]>("/backtests"),
  getBacktest: (backtestId: string) =>
    get<Backtest>(`/backtests/${encodeURIComponent(backtestId)}`),

  // AI analyses
  getAiAnalyses: () => get<AiAnalysis[]>("/ai"),
  getAiAnalysis: (analysisId: string) =>
    get<AiAnalysis>(`/ai/${encodeURIComponent(analysisId)}`),
};
