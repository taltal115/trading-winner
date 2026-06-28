from app.api.dependencies import AppContainer
from app.config.settings import Settings, SystemPhase


def _phase3_container() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.AI_INTEGRATION))


def _phase1_container() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY))


def test_phase3_pipeline_enriches_catalyst_ticker_only() -> None:
    container = _phase3_container()
    signals = container.pipeline_service.run_daily()
    by_ticker = {s.ticker: s for s in signals}

    # NVDA has a catalyst headline -> enriched with AI; AAPL has none -> not.
    assert by_ticker["NVDA"].ai_analysis_id is not None
    assert by_ticker["AAPL"].ai_analysis_id is None

    analyses = container.ai_repo.list()
    assert len(analyses) == 1
    assert analyses[0].related_id == by_ticker["NVDA"].id
    assert analyses[0].ticker == "NVDA"


def test_phase3_ai_analysis_is_traceable() -> None:
    container = _phase3_container()
    container.pipeline_service.run_daily()
    # Integrity holds: ai_analysis references a real signal, no orphans.
    assert container.integrity_service.find_orphans() == []


def test_phase3_decision_is_engine_derived_not_ai() -> None:
    container = _phase3_container()
    signals = container.pipeline_service.run_daily()
    nvda = next(s for s in signals if s.ticker == "NVDA")
    analysis = container.ai_repo.get(nvda.ai_analysis_id or "")
    assert analysis is not None
    # The AI supplies a bounded adjustment; the stored decision is still one of
    # the deterministic engine outcomes, never set directly by the AI.
    assert nvda.decision.value in {"STRONG_BUY", "BUY", "WATCH"}
    assert abs(analysis.confidence_adjustment) <= container.settings.ai_max_confidence_adjustment


def test_phase1_pipeline_does_not_call_ai() -> None:
    container = _phase1_container()
    signals = container.pipeline_service.run_daily()
    assert all(s.ai_analysis_id is None for s in signals)
    assert container.ai_repo.list() == []
