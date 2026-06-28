import pytest

from app.api.dependencies import _build_fundamental_source, _build_macro_source
from app.config.settings import Settings
from app.services.fundamental_data import MockFundamentalDataSource
from app.services.regime_data import MockMacroDataSource


def test_fundamental_source_defaults_to_mock() -> None:
    assert isinstance(_build_fundamental_source(Settings()), MockFundamentalDataSource)


def test_macro_source_defaults_to_mock() -> None:
    assert isinstance(_build_macro_source(Settings()), MockMacroDataSource)


def test_unknown_fundamental_backend_raises() -> None:
    with pytest.raises(NotImplementedError):
        _build_fundamental_source(Settings(fundamental_data_backend="finnhub"))


def test_unknown_regime_backend_raises() -> None:
    with pytest.raises(NotImplementedError):
        _build_macro_source(Settings(regime_data_backend="ibkr"))
