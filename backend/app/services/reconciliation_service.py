"""Reconciliation service: detect drift between our books and the broker.

Gathers internal open positions and broker-reported positions, runs the pure
reconciliation engine, and logs every discrepancy as a WARNING so drift is
visible in ``logs/`` and alertable. Detection only — it never mutates positions
(see reconciliation_engine for why remediation is a human/ops decision).
"""

from __future__ import annotations

from app.engines.reconciliation_engine import ReconciliationReport, reconcile
from app.models.enums import LogLevel
from app.repositories.repositories import PositionRepository
from app.services.broker import BrokerClient
from app.services.log_writer import LogWriter


class ReconciliationService:
    def __init__(
        self,
        position_repo: PositionRepository,
        broker: BrokerClient,
        log_writer: LogWriter,
    ) -> None:
        self._positions = position_repo
        self._broker = broker
        self._log = log_writer

    def reconcile(self) -> ReconciliationReport:
        internal = {p.ticker: p.quantity for p in self._positions.get_open()}
        broker = {bp.ticker: bp.quantity for bp in self._broker.get_positions()}

        report = reconcile(internal, broker)

        for drift in report.discrepancies:
            self._log.log(
                event="position_drift",
                message=(
                    f"{drift.ticker}: {drift.kind} "
                    f"(internal={drift.internal_quantity}, broker={drift.broker_quantity})"
                ),
                level=LogLevel.WARNING,
                metadata={
                    "ticker": drift.ticker,
                    "kind": drift.kind,
                    "internal_quantity": drift.internal_quantity,
                    "broker_quantity": drift.broker_quantity,
                },
            )

        self._log.log(
            event="reconciliation_completed",
            message=(
                f"in_sync={report.in_sync} matched={len(report.matched)} "
                f"discrepancies={len(report.discrepancies)}"
            ),
            level=LogLevel.INFO if report.in_sync else LogLevel.WARNING,
        )
        return report
