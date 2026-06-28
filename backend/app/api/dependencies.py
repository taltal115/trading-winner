"""Composition root.

Builds the object graph for a chosen storage backend and wires repositories and
services together. FastAPI routes depend only on services, never on stores or
repositories directly.
"""

from __future__ import annotations

from functools import lru_cache

from app.config.settings import Settings, SystemPhase, get_settings
from app.repositories.base import DocumentStore, InMemoryDocumentStore
from app.repositories.firestore_store import FirestoreDocumentStore
from app.repositories.repositories import (
    AiAnalysisRepository,
    BacktestRepository,
    EmbeddingRepository,
    FeatureRepository,
    LogRepository,
    NewsRepository,
    PortfolioRepository,
    PositionRepository,
    RiskDecisionRepository,
    SignalRepository,
    StockRepository,
    SystemStateRepository,
    TradeRepository,
)
from app.services.ai_provider import AIProvider, MockAIProvider
from app.services.ai_service import AIService
from app.services.backtest_service import BacktestService
from app.services.broker import BrokerClient, MockBroker
from app.services.embedding_provider import EmbeddingProvider, MockEmbeddingProvider
from app.services.execution_service import ExecutionService
from app.services.feature_service import FeatureService
from app.services.ibkr_broker import IBKRBroker
from app.services.ibkr_market_data import IBKRMarketDataSource
from app.services.ingestion_service import IngestionService
from app.services.integrity_service import IntegrityService
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource, MockMarketDataSource
from app.services.news_service import NewsService
from app.services.openai_embedding_provider import OpenAIEmbeddingProvider
from app.services.openai_provider import OpenAIProvider
from app.services.pipeline_service import PipelineService
from app.services.portfolio_service import PortfolioService
from app.services.position_monitor_service import PositionMonitorService
from app.services.reconciliation_service import ReconciliationService
from app.services.retrieval_service import RetrievalService
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService
from app.services.trading_guard_service import TradingGuardService


def _build_store(settings: Settings) -> DocumentStore:
    if settings.repository_backend == "memory":
        return InMemoryDocumentStore()
    if settings.repository_backend == "firestore":
        return FirestoreDocumentStore(settings.firestore_project)
    raise NotImplementedError(
        f"repository_backend {settings.repository_backend!r} not implemented yet"
    )


def _build_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider_backend == "mock":
        return MockAIProvider()
    if settings.ai_provider_backend == "openai":
        return OpenAIProvider(settings.openai_model)
    raise NotImplementedError(
        f"ai_provider_backend {settings.ai_provider_backend!r} not implemented yet"
    )


def _build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_backend == "mock":
        return MockEmbeddingProvider()
    if settings.embedding_backend == "openai":
        return OpenAIEmbeddingProvider(settings.embedding_model)
    raise NotImplementedError(
        f"embedding_backend {settings.embedding_backend!r} not implemented yet"
    )


def _build_broker(settings: Settings) -> BrokerClient:
    if settings.broker_backend == "mock":
        return MockBroker()
    if settings.broker_backend == "ibkr":
        return IBKRBroker(settings.ibkr_host, settings.ibkr_port, settings.ibkr_broker_client_id)
    raise NotImplementedError(f"broker_backend {settings.broker_backend!r} not implemented yet")


def _build_source(settings: Settings) -> MarketDataSource:
    if settings.market_data_backend == "mock":
        return MockMarketDataSource()
    if settings.market_data_backend == "ibkr":
        return IBKRMarketDataSource(
            settings.ibkr_host, settings.ibkr_port, settings.ibkr_market_data_client_id
        )
    raise NotImplementedError(
        f"market_data_backend {settings.market_data_backend!r} not implemented yet"
    )


class AppContainer:
    """Holds singletons for the application's lifetime."""

    def __init__(
        self,
        settings: Settings,
        source: MarketDataSource | None = None,
        ai_provider: AIProvider | None = None,
        broker: BrokerClient | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings
        self.store = _build_store(settings)
        self.source: MarketDataSource = source or _build_source(settings)
        self.ai_provider: AIProvider = ai_provider or _build_ai_provider(settings)
        self.broker: BrokerClient = broker or _build_broker(settings)
        self.embedding_provider: EmbeddingProvider = (
            embedding_provider or _build_embedding_provider(settings)
        )

        self.stock_repo = StockRepository(self.store)
        self.feature_repo = FeatureRepository(self.store)
        self.signal_repo = SignalRepository(self.store)
        self.trade_repo = TradeRepository(self.store)
        self.ai_repo = AiAnalysisRepository(self.store)
        self.embedding_repo = EmbeddingRepository(self.store)
        self.news_repo = NewsRepository(self.store)
        self.risk_repo = RiskDecisionRepository(self.store)
        self.position_repo = PositionRepository(self.store)
        self.portfolio_repo = PortfolioRepository(self.store)
        self.backtest_repo = BacktestRepository(self.store)
        self.system_state_repo = SystemStateRepository(self.store)
        self.log_repo = LogRepository(self.store)

        self.ingestion_service = IngestionService(
            self.stock_repo, LogWriter("ingestion_service", self.log_repo), self.source
        )
        self.feature_service = FeatureService(
            self.feature_repo, LogWriter("feature_service", self.log_repo), self.source
        )
        self.signal_service = SignalService(
            self.signal_repo, LogWriter("signal_engine", self.log_repo)
        )
        self.integrity_service = IntegrityService(
            self.feature_repo, self.signal_repo, self.trade_repo, self.ai_repo
        )
        self.news_service = NewsService(
            self.news_repo, LogWriter("news_service", self.log_repo), self.source
        )
        self.retrieval_service = RetrievalService(
            self.news_repo,
            self.ai_repo,
            self.embedding_repo,
            self.embedding_provider,
            LogWriter("retrieval_service", self.log_repo),
            settings.retrieval_top_k,
        )
        self.ai_service = AIService(
            self.ai_repo,
            LogWriter("ai_pipeline", self.log_repo),
            self.ai_provider,
            settings,
            retrieval_service=self.retrieval_service if settings.retrieval_enabled else None,
        )
        self.portfolio_service = PortfolioService(
            self.portfolio_repo, self.position_repo, LogWriter("portfolio_service", self.log_repo)
        )
        self.risk_service = RiskService(
            self.risk_repo,
            self.stock_repo,
            self.portfolio_service,
            LogWriter("risk_engine", self.log_repo),
            settings.risk,
        )
        self.execution_service = ExecutionService(
            self.trade_repo,
            self.stock_repo,
            self.broker,
            self.integrity_service,
            self.portfolio_service,
            LogWriter("execution_engine", self.log_repo),
            settings,
        )
        self.position_monitor_service = PositionMonitorService(
            self.position_repo,
            self.trade_repo,
            self.portfolio_service,
            self.broker,
            self.source,
            LogWriter("position_monitor", self.log_repo),
            settings.exit,
        )
        self.trading_guard_service = TradingGuardService(
            self.system_state_repo,
            self.trade_repo,
            self.portfolio_service,
            LogWriter("trading_guard", self.log_repo),
            settings.safety,
        )
        self.reconciliation_service = ReconciliationService(
            self.position_repo,
            self.broker,
            LogWriter("reconciliation", self.log_repo),
        )

        # Later stages are wired into the pipeline only from their phase onward.
        ai_enabled = settings.phase >= SystemPhase.AI_INTEGRATION
        execution_enabled = settings.phase >= SystemPhase.RISK_EXECUTION
        self.pipeline_service = PipelineService(
            self.ingestion_service,
            self.feature_service,
            self.signal_service,
            LogWriter("pipeline_service", self.log_repo),
            news_service=self.news_service if ai_enabled else None,
            ai_service=self.ai_service if ai_enabled else None,
            risk_service=self.risk_service if execution_enabled else None,
            execution_service=self.execution_service if execution_enabled else None,
            source=self.source if execution_enabled else None,
            trading_guard=self.trading_guard_service if execution_enabled else None,
        )
        self.backtest_service = BacktestService(
            self.backtest_repo, LogWriter("backtest_service", self.log_repo), self.source
        )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer(get_settings())


def get_signal_service() -> SignalService:
    return get_container().signal_service


def get_pipeline_service() -> PipelineService:
    return get_container().pipeline_service


def get_backtest_service() -> BacktestService:
    return get_container().backtest_service


def get_ai_service() -> AIService:
    return get_container().ai_service


def get_portfolio_service() -> PortfolioService:
    return get_container().portfolio_service


def get_position_monitor_service() -> PositionMonitorService:
    return get_container().position_monitor_service


def get_trading_guard_service() -> TradingGuardService:
    return get_container().trading_guard_service


def get_reconciliation_service() -> ReconciliationService:
    return get_container().reconciliation_service
