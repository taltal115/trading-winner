"""Human-readable, debuggable ID helpers.

Per DATABASE.md we never use random/hash IDs. Formats:

    {entity}_{ticker}_{date}            e.g. signal_NVDA_2026-07-28
    {entity}_{ticker}_{date}_{time}     e.g. trade_NVDA_2026-07-28_093015
    {entity}_{ticker}_{date}_{seq}      e.g. news_NVDA_2026-07-28_1
"""

from __future__ import annotations

import re
from datetime import date, datetime

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_DATE_RE = r"\d{4}-\d{2}-\d{2}"
_TIME_RE = r"\d{6}"

# Ticker-scoped form: {entity}_{TICKER}_{date}[_{time|seq}]
TICKER_ID_RE = re.compile(
    rf"^[a-z][a-z_]*_[A-Z][A-Z0-9.\-]{{0,9}}_{_DATE_RE}(?:_(?:{_TIME_RE}|\d+))?$"
)
# Generic readable form: {entity}_{slug}
GENERIC_ID_RE = re.compile(r"^[a-z][a-z_]*_[A-Za-z0-9][A-Za-z0-9._-]*$")
# Reject opaque hashes (long hex with no human-readable separators).
_HASH_RE = re.compile(r"(?:^|_)[0-9a-f]{16,}$")


def validate_ticker(ticker: str) -> str:
    """Return the ticker if valid, else raise ValueError."""
    if not TICKER_RE.match(ticker):
        raise ValueError(f"Invalid ticker: {ticker!r}")
    return ticker


def _date_part(when: date | datetime) -> str:
    if isinstance(when, datetime):
        return when.date().isoformat()
    return when.isoformat()


def feature_id(ticker: str, when: date | datetime) -> str:
    return f"feature_{validate_ticker(ticker)}_{_date_part(when)}"


def signal_id(ticker: str, when: date | datetime) -> str:
    return f"signal_{validate_ticker(ticker)}_{_date_part(when)}"


def trade_id(ticker: str, when: datetime) -> str:
    return f"trade_{validate_ticker(ticker)}_{when.strftime('%Y-%m-%d_%H%M%S')}"


def news_id(ticker: str, when: date | datetime, sequence: int) -> str:
    return f"news_{validate_ticker(ticker)}_{_date_part(when)}_{sequence}"


def ai_analysis_id(ticker: str, when: date | datetime) -> str:
    return f"ai_{validate_ticker(ticker)}_{_date_part(when)}"


def embedding_id(source_id: str) -> str:
    """Deterministic id for a cached embedding, keyed on its source document."""
    return f"embedding_{source_id}"


def risk_decision_id(ticker: str, when: datetime) -> str:
    return f"risk_{validate_ticker(ticker)}_{when.strftime('%Y-%m-%d_%H%M%S')}"


def position_id(ticker: str, when: date | datetime) -> str:
    return f"position_{validate_ticker(ticker)}_{_date_part(when)}"


def portfolio_id(name: str) -> str:
    return f"portfolio_{name}"


def system_state_id(name: str = "main") -> str:
    return f"system_state_{name}"


def order_id(ticker: str, when: datetime) -> str:
    """Deterministic client order id -> idempotent broker submission."""
    return f"order_{validate_ticker(ticker)}_{when.strftime('%Y-%m-%d_%H%M%S')}"


def exit_order_id(ticker: str, opened_at: datetime) -> str:
    """Deterministic exit (sell-to-close) order id, keyed on entry time.

    Distinct from the entry ``order_id`` (``_exit`` suffix) and stable across
    retries so a re-run of the monitor never double-submits a close.
    """
    return f"order_{validate_ticker(ticker)}_{opened_at.strftime('%Y-%m-%d_%H%M%S')}_exit"


def backtest_id(strategy: str, start: date) -> str:
    return f"backtest_{strategy}_{start.isoformat()}"


def job_id(job_type: str, when: datetime) -> str:
    return f"job_{job_type}_{when.strftime('%Y-%m-%d_%H%M%S')}"


def log_id(service: str, when: datetime, sequence: int) -> str:
    return f"log_{service}_{when.strftime('%Y-%m-%d_%H%M%S')}_{sequence}"


def is_valid_id(value: str) -> bool:
    if _HASH_RE.search(value):
        return False
    return bool(TICKER_ID_RE.match(value) or GENERIC_ID_RE.match(value))
