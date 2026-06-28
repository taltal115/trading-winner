"""Pipeline trigger endpoint (ops).

Runs the deterministic Phase 1 pipeline (ingest -> features -> signals). This
never executes trades; it only produces signals.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_pipeline_service
from app.models.entities import Signal
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

PipelineServiceDep = Annotated[PipelineService, Depends(get_pipeline_service)]


@router.post("/run")
def run_pipeline(service: PipelineServiceDep) -> list[Signal]:
    return service.run_daily()
