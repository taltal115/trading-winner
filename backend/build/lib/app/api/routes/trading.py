"""Trading safety controls: status + manual kill switch (ops only).

The kill switch is an operator override that halts NEW entries. It never forces
trades and never closes positions; exits keep running so open risk stays
manageable while halted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import AppContainer, get_container

router = APIRouter(prefix="/trading", tags=["trading"])

ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("/status")
def trading_status(container: ContainerDep) -> dict[str, object]:
    guard = container.trading_guard_service
    state = guard.get_state()
    assessment = guard.assess()
    return {
        "halted": assessment.halted,
        "reasons": assessment.reasons,
        "kill_switch_enabled": state.kill_switch_enabled,
        "halt_reason": state.halt_reason,
    }


@router.post("/halt")
def halt_trading(container: ContainerDep, reason: str = "manual halt") -> dict[str, object]:
    state = container.trading_guard_service.engage_kill_switch(reason)
    return {"kill_switch_enabled": state.kill_switch_enabled, "halt_reason": state.halt_reason}


@router.post("/resume")
def resume_trading(container: ContainerDep) -> dict[str, object]:
    state = container.trading_guard_service.release_kill_switch()
    return {"kill_switch_enabled": state.kill_switch_enabled, "halt_reason": state.halt_reason}
