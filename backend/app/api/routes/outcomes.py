"""Read-only outcome endpoints (learning loop, Phase 6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import AppContainer, get_container
from app.models.entities import TradeOutcome

router = APIRouter(prefix="/outcomes", tags=["outcomes"])

ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("")
def list_outcomes(container: ContainerDep) -> list[TradeOutcome]:
    """Return recorded trade outcomes, most recently exited first."""
    return container.outcome_service.list_outcomes()


@router.get("/{outcome_id}")
def get_outcome(outcome_id: str, container: ContainerDep) -> TradeOutcome:
    outcome = container.outcome_service.get_outcome(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"outcome {outcome_id} not found")
    return outcome
