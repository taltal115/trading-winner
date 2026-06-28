"""Read-only signal endpoints. The UI consumes these; it never computes them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_signal_service
from app.models.entities import Signal
from app.services.signal_service import SignalService

router = APIRouter(prefix="/signals", tags=["signals"])

SignalServiceDep = Annotated[SignalService, Depends(get_signal_service)]


@router.get("")
def list_top_signals(
    service: SignalServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Signal]:
    return service.get_top_signals(limit=limit)


@router.get("/{signal_id}")
def get_signal(
    signal_id: str,
    service: SignalServiceDep,
) -> Signal:
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"signal {signal_id} not found")
    return signal
