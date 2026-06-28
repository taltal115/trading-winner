"""Central application configuration.

Settings are environment-driven (dev / staging / prod) and phase-aware. The
phase gate enforces the documented execution-dependency rule:

- Phase 1: quant-only signals; ``ai_analysis_id`` optional.
- Phase 3+: ``ai_analysis_id`` required before any execution.
- Phase 4+: risk validation required before any execution.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class SystemPhase(IntEnum):
    """Implementation phase. Controls execution-dependency strictness."""

    MVP_READ_ONLY = 1
    BACKTESTING = 2
    AI_INTEGRATION = 3
    RISK_EXECUTION = 4
    STAGING = 5
    PRODUCTION = 6


class RiskLimits(BaseSettings):
    """Hard risk limits sourced from TRADING_ENGINE.md."""

    risk_per_trade: float = 0.01
    max_open_positions: int = 15
    max_sector_exposure: float = 0.25
    max_single_position: float = 0.10
    cash_buffer_minimum: float = 0.10
    min_hold_hours: int = 24
    max_intraday_round_trips_per_week: int = 3


class ExitLimits(BaseSettings):
    """Live exit parameters (TRADING_ENGINE.md section 8).

    These mirror the backtest defaults so live and historical exits run through
    the SAME exit engine with identical thresholds (.cursor/rules.md 3.2 / 9).
    """

    max_hold_days: int = 10
    profit_target: float = 0.12


class SafetyLimits(BaseSettings):
    """Account-level safety governor limits (.cursor/rules.md section 6).

    These are deterministic circuit breakers that halt NEW entries; they are
    distinct from the per-trade RiskLimits and complement, never replace, them.
    Exits continue to run while halted so open risk can still be reduced.
    """

    max_daily_loss: float = 0.06  # halt if realized loss today >= 6% of equity
    max_consecutive_losses: int = 4  # halt after N losing trades in a row


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEV
    phase: SystemPhase = SystemPhase.MVP_READ_ONLY
    repository_backend: str = "memory"  # "memory" | "firestore"
    # GCP project for the Firestore backend. None -> the SDK infers it from the
    # ambient credentials / FIRESTORE_EMULATOR_HOST (dev emulator).
    firestore_project: str | None = None
    risk: RiskLimits = RiskLimits()
    exit: ExitLimits = ExitLimits()
    safety: SafetyLimits = SafetyLimits()

    # AI provider backend selection: "mock" (deterministic, default) | "openai".
    ai_provider_backend: str = "mock"
    openai_model: str = "gpt-5"

    # Live broker + market-data backends: "mock" (deterministic, default) | "ibkr".
    # The IBKR adapters connect to a local TWS / IB Gateway; distinct client ids
    # keep the broker and market-data sessions independent on the same gateway.
    broker_backend: str = "mock"
    market_data_backend: str = "mock"
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_broker_client_id: int = 1
    ibkr_market_data_client_id: int = 2

    # AI is only consulted when a signal's quant score clears this threshold AND
    # a catalyst is present (AI_PIPELINE.md section 2.2 cost control).
    ai_score_threshold: float = 50.0
    # Maximum |confidence_adjustment| the AI layer may apply to a score.
    ai_max_confidence_adjustment: float = 0.20

    # RAG retrieval (AI_PIPELINE.md sections 5/8): inject similar prior documents
    # into the reasoning prompt. Off by default; enrichment-only, never gating.
    retrieval_enabled: bool = False
    retrieval_top_k: int = 5
    embedding_backend: str = "mock"  # "mock" (deterministic, default) | "openai"
    embedding_model: str = "text-embedding-3-large"

    @property
    def ai_required_for_execution(self) -> bool:
        return self.phase >= SystemPhase.AI_INTEGRATION

    @property
    def risk_required_for_execution(self) -> bool:
        return self.phase >= SystemPhase.RISK_EXECUTION

    @property
    def position_monitoring_enabled(self) -> bool:
        """Live exit/position-monitor worker runs from Phase 5 (staging) onward."""
        return self.phase >= SystemPhase.STAGING

    @property
    def reconciliation_enabled(self) -> bool:
        """Broker position reconciliation runs from Phase 5 (staging) onward."""
        return self.phase >= SystemPhase.STAGING


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
