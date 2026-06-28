from app.api.dependencies import AppContainer
from app.config.settings import Settings, SystemPhase
from app.engines.market_regime_engine import MarketRegimeInputs
from app.models.ai import AIPromptContext
from app.models.entities import Signal
from app.models.enums import ExposureRecommendation, RegimeState
from app.services.ai_provider import MockAIProvider


class _StressedMacroSource:
    """Deterministic high-volatility macro environment (regime risk-off)."""

    def get_market_regime_inputs(self) -> MarketRegimeInputs:
        return MarketRegimeInputs(
            spy_trend=-0.02,
            vix=35.0,
            sector_breadth=0.3,
            market_momentum=-0.04,
            cross_stock_correlation=0.85,
        )


class _CapturingAIProvider:
    """Wraps the mock provider but records each prompt context."""

    reasoning_version = "mock-v1"
    prompt_version = "1.0"

    def __init__(self) -> None:
        self._mock = MockAIProvider()
        self.contexts: list[AIPromptContext] = []

    def analyze(self, context: AIPromptContext) -> dict[str, object]:
        self.contexts.append(context)
        return self._mock.analyze(context)


def _signals_by_ticker(container: AppContainer) -> dict[str, Signal]:
    return {s.ticker: s for s in container.pipeline_service.run_daily()}


# --- Regression: flags OFF leave everything unchanged ------------------------


def test_flags_off_compute_nothing_new() -> None:
    container = AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY))
    signals = container.pipeline_service.run_daily()
    assert container.fundamental_repo.list() == []
    assert container.market_regime_repo.list() == []
    assert all(s.fundamental_id is None for s in signals)
    assert all(s.market_regime_id is None for s in signals)


def test_flags_off_scores_match_baseline() -> None:
    base = _signals_by_ticker(AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY)))
    # A second default container must reproduce identical scores (determinism).
    again = _signals_by_ticker(AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY)))
    assert {t: s.score for t, s in base.items()} == {t: s.score for t, s in again.items()}


# --- Fundamental Engine ON: quality bias + traceability ----------------------


def test_fundamental_filter_applies_quality_bias() -> None:
    baseline = _signals_by_ticker(AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY)))
    biased_container = AppContainer(
        Settings(phase=SystemPhase.MVP_READ_ONLY, fundamental_filter_enabled=True)
    )
    biased = _signals_by_ticker(biased_container)

    # NVDA is high-quality in the mock -> bounded quality boost.
    assert biased["NVDA"].score > baseline["NVDA"].score
    assert biased["NVDA"].fundamental_id == "fundamental_NVDA_2026-07-28"
    assert biased_container.fundamental_repo.get("fundamental_NVDA_2026-07-28") is not None


# --- Market Regime Engine ON: persisted + threaded ---------------------------


def test_regime_snapshot_persisted_and_referenced() -> None:
    container = AppContainer(
        Settings(phase=SystemPhase.AI_INTEGRATION, regime_adjustment_enabled=True),
        macro_source=_StressedMacroSource(),
    )
    signals = container.pipeline_service.run_daily()
    regime = container.market_regime_repo.get_latest()
    assert regime is not None
    assert regime.id == "regime_2026-07-28"
    assert regime.regime_state is RegimeState.HIGH_VOLATILITY
    assert regime.exposure_recommendation is ExposureRecommendation.LOW
    assert regime.risk_multiplier <= 0.75
    assert all(s.market_regime_id == "regime_2026-07-28" for s in signals)


def test_engines_on_keep_traceability_intact() -> None:
    container = AppContainer(
        Settings(
            phase=SystemPhase.AI_INTEGRATION,
            fundamental_filter_enabled=True,
            regime_adjustment_enabled=True,
        )
    )
    container.pipeline_service.run_daily()
    assert container.integrity_service.find_orphans() == []


# --- AI context carries the new read-only fields -----------------------------


def test_ai_context_carries_fundamental_and_regime() -> None:
    provider = _CapturingAIProvider()
    container = AppContainer(
        Settings(
            phase=SystemPhase.AI_INTEGRATION,
            fundamental_filter_enabled=True,
            regime_adjustment_enabled=True,
        ),
        ai_provider=provider,
    )
    container.pipeline_service.run_daily()

    nvda_context = next(c for c in provider.contexts if c.ticker == "NVDA")
    assert nvda_context.fundamental_score is not None
    assert nvda_context.fundamental_score > 80.0
    assert nvda_context.regime_state == RegimeState.NEUTRAL.value
