"""Fundamental Engine (ARCHITECTURE.md 3.2.1, TRADING_ENGINE.md 4.4/4.5).

Pure and deterministic: no I/O, no storage. Evaluates long-term financial
health and produces a Quality Score (0-100) used as a *bounded* swing-trading
quality bias/filter -- NOT a long-term investing decision engine and NEVER an
execution authority. The QualityBias and hard veto here are applied to the
scoring path deterministically, BEFORE any AI enrichment (TRADING_ENGINE.md
6.1). It never places trades and never overrides the Risk Engine.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import QualitySubscores

# Quality subscore weights for the blended fundamental_score (must sum to 1.0).
WEIGHT_PROFITABILITY = 0.30
WEIGHT_GROWTH = 0.25
WEIGHT_LEVERAGE = 0.25
WEIGHT_CASHFLOW = 0.20

# Hard fundamental filter threshold (TRADING_ENGINE.md 4.5 / 6.1): a candidate
# with fundamental_score below this (or a bankruptcy flag) is forced to IGNORE.
FUNDAMENTAL_VETO_SCORE = 20.0

# Dilution flag: shares outstanding up more than this fraction year-over-year.
_DILUTION_THRESHOLD = 0.05

# Risk-flag identifiers (enumerated, stable strings for Firestore).
BANKRUPTCY_RISK = "bankruptcy_risk"
DILUTION_RISK = "dilution_risk"


class FundamentalInputs(BaseModel):
    """Raw financial inputs for one ticker (from the fundamentals data seam)."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    # Financial statements (trailing-twelve-month, with prior-year comparatives).
    revenue_ttm: float
    revenue_prior_ttm: float
    earnings_ttm: float
    earnings_prior_ttm: float
    # Cashflow.
    operating_cashflow_ttm: float
    free_cashflow_ttm: float
    # Balance sheet / leverage.
    total_debt: float
    total_equity: float
    debt_to_equity: float
    current_ratio: float
    # Profitability.
    net_margin: float  # net income / revenue
    return_on_equity: float
    # Dilution / share-issuance trend.
    shares_outstanding: float
    shares_outstanding_prior: float


class FundamentalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fundamental_score: float = Field(ge=0.0, le=100.0)
    quality_subscores: QualitySubscores
    risk_flags: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _growth_rate(current: float, prior: float) -> float:
    """Year-over-year growth, robust to non-positive/zero prior periods."""
    if prior == 0.0:
        return 0.0
    return (current - prior) / abs(prior)


def compute_profitability_score(inputs: FundamentalInputs) -> float:
    """Blend net margin and return-on-equity (higher is healthier)."""
    margin_component = _clamp(50.0 + inputs.net_margin * 250.0)
    roe_component = _clamp(50.0 + inputs.return_on_equity * 200.0)
    return _clamp(0.5 * margin_component + 0.5 * roe_component)


def compute_growth_score(inputs: FundamentalInputs) -> float:
    """Blend revenue and earnings growth; revenue weighted slightly higher."""
    revenue_growth = _growth_rate(inputs.revenue_ttm, inputs.revenue_prior_ttm)
    earnings_growth = _growth_rate(inputs.earnings_ttm, inputs.earnings_prior_ttm)
    return _clamp(50.0 + revenue_growth * 200.0 * 0.6 + earnings_growth * 200.0 * 0.4)


def compute_leverage_score(inputs: FundamentalInputs) -> float:
    """Lower leverage and stronger liquidity are healthier."""
    debt_component = _clamp(100.0 - inputs.debt_to_equity * 40.0)
    liquidity_component = _clamp(inputs.current_ratio / 2.0 * 100.0)
    return _clamp(0.7 * debt_component + 0.3 * liquidity_component)


def compute_cashflow_score(inputs: FundamentalInputs) -> float:
    """Operating cashflow margin plus a free-cashflow positivity bonus."""
    revenue = inputs.revenue_ttm
    ocf_margin = inputs.operating_cashflow_ttm / revenue if revenue > 0 else 0.0
    ocf_component = _clamp(ocf_margin * 300.0)
    fcf_component = 100.0 if inputs.free_cashflow_ttm > 0 else 0.0
    return _clamp(0.6 * ocf_component + 0.4 * fcf_component)


def detect_risk_flags(inputs: FundamentalInputs) -> list[str]:
    """Deterministic enumerated risk flags (e.g. bankruptcy_risk, dilution_risk)."""
    flags: list[str] = []
    bankruptcy = inputs.total_equity <= 0.0 or (
        inputs.current_ratio < 1.0 and inputs.debt_to_equity > 2.5 and inputs.earnings_ttm < 0.0
    )
    if bankruptcy:
        flags.append(BANKRUPTCY_RISK)
    if inputs.shares_outstanding > inputs.shares_outstanding_prior * (1.0 + _DILUTION_THRESHOLD):
        flags.append(DILUTION_RISK)
    return flags


def evaluate_fundamentals(inputs: FundamentalInputs) -> FundamentalResult:
    """Produce the full deterministic fundamental result for a ticker."""
    subscores = QualitySubscores(
        profitability_score=round(compute_profitability_score(inputs), 4),
        growth_score=round(compute_growth_score(inputs), 4),
        leverage_score=round(compute_leverage_score(inputs), 4),
        cashflow_score=round(compute_cashflow_score(inputs), 4),
    )
    fundamental_score = (
        WEIGHT_PROFITABILITY * subscores.profitability_score
        + WEIGHT_GROWTH * subscores.growth_score
        + WEIGHT_LEVERAGE * subscores.leverage_score
        + WEIGHT_CASHFLOW * subscores.cashflow_score
    )
    return FundamentalResult(
        fundamental_score=round(_clamp(fundamental_score), 4),
        quality_subscores=subscores,
        risk_flags=detect_risk_flags(inputs),
    )


def compute_quality_bias(fundamental_score: float) -> float:
    """Bounded quality bias in [0.9, 1.1] (TRADING_ENGINE.md 4.4).

    QualityBias = 0.9 + 0.2 * (fundamental_score / 100). High-quality names get
    a mild boost (<=+10%); low-quality names get a mild penalty (>=-10%).
    """
    return 0.9 + 0.2 * (_clamp(fundamental_score) / 100.0)


def is_vetoed(result: FundamentalResult, min_score: float = FUNDAMENTAL_VETO_SCORE) -> bool:
    """Hard fundamental filter (TRADING_ENGINE.md 4.5 / 6.1).

    Bankruptcy risk OR fundamental_score below ``min_score`` forces IGNORE,
    regardless of any other score or AI output.
    """
    return BANKRUPTCY_RISK in result.risk_flags or result.fundamental_score < min_score


def shares_outstanding_trend(inputs: FundamentalInputs) -> str:
    """Human-readable dilution trend for the snapshot's inputs_summary."""
    if inputs.shares_outstanding > inputs.shares_outstanding_prior * (1.0 + _DILUTION_THRESHOLD):
        return "rising"
    if inputs.shares_outstanding < inputs.shares_outstanding_prior * (1.0 - _DILUTION_THRESHOLD):
        return "falling"
    return "stable"
