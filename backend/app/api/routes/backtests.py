"""Backtest endpoints: trigger a run (ops) and read results (UI)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import get_backtest_service
from app.models.entities import Backtest
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])

BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]


class BacktestRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)
    strategy: str = "momentum_catalyst_v1"


@router.post("/run")
def run_backtest(request: BacktestRequest, service: BacktestServiceDep) -> Backtest:
    return service.run_backtest(tickers=request.tickers, strategy=request.strategy)


@router.get("")
def list_backtests(
    service: BacktestServiceDep,
    strategy: str | None = None,
) -> list[Backtest]:
    return service.list_backtests(strategy=strategy)


@router.get("/{backtest_id}")
def get_backtest(backtest_id: str, service: BacktestServiceDep) -> Backtest:
    result = service.get_backtest(backtest_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"backtest {backtest_id} not found")
    return result
