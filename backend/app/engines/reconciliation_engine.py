"""Position reconciliation (ARCHITECTURE.md 3.6: "sync portfolio state").

Pure, deterministic comparison of the system's internal open positions against
the broker's reported truth. Detection only: it classifies drift but never
mutates state. Remediation is deliberately a human/ops decision because silently
"fixing" a position could fabricate an untraceable holding (.cursor/rules.md 12).

Discrepancy kinds:
- ``quantity_mismatch``  : same ticker held by both, different quantity.
- ``missing_at_broker``  : we think we hold it, broker does not (phantom).
- ``untracked_internally``: broker holds it, we have no position record.
"""

from __future__ import annotations

from math import isclose

from pydantic import BaseModel, ConfigDict, Field

_QTY_TOLERANCE = 1e-9


class PositionDiscrepancy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    kind: str
    internal_quantity: float
    broker_quantity: float


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_sync: bool
    matched: list[str] = Field(default_factory=list)
    discrepancies: list[PositionDiscrepancy] = Field(default_factory=list)


def reconcile(
    internal: dict[str, float],
    broker: dict[str, float],
) -> ReconciliationReport:
    """Compare internal vs broker quantities by ticker and classify any drift."""
    matched: list[str] = []
    discrepancies: list[PositionDiscrepancy] = []

    for ticker in sorted(set(internal) | set(broker)):
        internal_qty = internal.get(ticker, 0.0)
        broker_qty = broker.get(ticker, 0.0)

        if isclose(internal_qty, broker_qty, abs_tol=_QTY_TOLERANCE):
            matched.append(ticker)
            continue

        if internal_qty > 0 and broker_qty <= 0:
            kind = "missing_at_broker"
        elif broker_qty > 0 and internal_qty <= 0:
            kind = "untracked_internally"
        else:
            kind = "quantity_mismatch"

        discrepancies.append(
            PositionDiscrepancy(
                ticker=ticker,
                kind=kind,
                internal_quantity=internal_qty,
                broker_quantity=broker_qty,
            )
        )

    return ReconciliationReport(
        in_sync=not discrepancies,
        matched=matched,
        discrepancies=discrepancies,
    )
