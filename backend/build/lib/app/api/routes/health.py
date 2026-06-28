"""Health and system-status endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import AppContainer, get_container
from app.config.settings import get_settings

router = APIRouter(tags=["system"])

ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "phase": int(settings.phase),
    }


@router.get("/system/integrity")
def integrity(container: ContainerDep) -> dict[str, object]:
    violations = container.integrity_service.find_orphans()
    return {"ok": not violations, "violations": violations}
