"""Read-only AI reasoning endpoints (UI /ai page consumes these)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_ai_service
from app.models.entities import AiAnalysis
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])

AIServiceDep = Annotated[AIService, Depends(get_ai_service)]


@router.get("")
def list_ai_analyses(service: AIServiceDep) -> list[AiAnalysis]:
    return service.list_analyses()


@router.get("/{analysis_id}")
def get_ai_analysis(analysis_id: str, service: AIServiceDep) -> AiAnalysis:
    analysis = service.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"ai_analysis {analysis_id} not found")
    return analysis
