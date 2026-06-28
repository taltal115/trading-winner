"""Read-only portfolio, positions, and trade endpoints (UI consumes these)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import AppContainer, get_container
from app.engines.reconciliation_engine import ReconciliationReport
from app.models.entities import Position, Trade

router = APIRouter(tags=["portfolio"])

ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("/portfolio")
def get_portfolio(container: ContainerDep) -> dict[str, object]:
    portfolio = container.portfolio_service.get_or_create_portfolio()
    positions = container.portfolio_service.open_positions()
    return {
        "equity": portfolio.equity,
        "cash": portfolio.cash,
        "open_positions": len(positions),
        "exposure": round(sum(p.market_value for p in positions), 2),
        "updated_at": portfolio.updated_at.isoformat(),
    }


@router.get("/positions")
def list_positions(container: ContainerDep) -> list[Position]:
    return container.portfolio_service.open_positions()


@router.get("/trades")
def list_trades(container: ContainerDep) -> list[Trade]:
    return container.trade_repo.list()


@router.post("/positions/monitor")
def monitor_positions(container: ContainerDep) -> list[Trade]:
    """Ops trigger for the live exit pass. Returns positions closed this run."""
    return container.position_monitor_service.monitor_positions()


@router.get("/positions/reconcile")
def reconcile_positions(container: ContainerDep) -> ReconciliationReport:
    """Detect drift between internal positions and broker truth (read-only)."""
    return container.reconciliation_service.reconcile()
