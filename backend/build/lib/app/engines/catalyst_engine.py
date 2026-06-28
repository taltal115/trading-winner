"""Catalyst detection engine (AI_PIPELINE.md section 9).

Pure, deterministic keyword trigger detection. This runs BEFORE any GPT call
and is the primary cost-control gate: no catalyst -> no AI call. It never makes
a trading decision; it only decides whether unstructured context is worth the
(expensive) reasoning step.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.entities import NewsItem
from app.models.enums import CatalystType

# Trigger phrases mapped to a catalyst type. Lowercased substring match.
_TRIGGERS: dict[str, CatalystType] = {
    "announces": CatalystType.NEWS,
    "announced": CatalystType.NEWS,
    "partnership": CatalystType.NEWS,
    "contract awarded": CatalystType.NEWS,
    "beats expectations": CatalystType.EARNINGS,
    "earnings": CatalystType.EARNINGS,
    "guidance raised": CatalystType.EARNINGS,
    "guidance cut": CatalystType.EARNINGS,
    "fda approval": CatalystType.NEWS,
    "8-k": CatalystType.NEWS,
    "insider": CatalystType.INSIDER,
}


class CatalystResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected: bool
    catalyst_type: CatalystType
    matched_terms: list[str]


def detect_catalyst(news: list[NewsItem]) -> CatalystResult:
    """Scan headlines for trigger phrases and classify the catalyst type."""
    matched: list[str] = []
    catalyst_type = CatalystType.UNKNOWN
    for item in news:
        headline = item.headline.lower()
        for term, term_type in _TRIGGERS.items():
            if term in headline and term not in matched:
                matched.append(term)
                if catalyst_type == CatalystType.UNKNOWN:
                    catalyst_type = term_type
    return CatalystResult(
        detected=bool(matched),
        catalyst_type=catalyst_type,
        matched_terms=matched,
    )
