"""Scheduled reconciliation worker (Phase 5).

Thin job entrypoint that detects drift between internal positions and broker
truth (ARCHITECTURE.md section 7 scheduled jobs). Read-only and idempotent: it
logs discrepancies but never mutates state, so re-running is always safe. Each
run is wrapped in a ``JobRecord`` for audit and gated to Phase 5+.

Run manually:
    python -m app.workers.reconciliation
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.dependencies import AppContainer, get_container
from app.engines.reconciliation_engine import ReconciliationReport
from app.models.entities import JobRecord
from app.models.enums import JobStatus, LogLevel
from app.repositories.repositories import JobRepository
from app.services.log_writer import LogWriter
from app.utils.ids import job_id

_JOB_TYPE = "reconciliation"


def run_reconciliation(container: AppContainer | None = None) -> ReconciliationReport | None:
    """Run one reconciliation pass under a tracked job. Returns the report."""
    container = container or get_container()
    log = LogWriter(_JOB_TYPE, container.log_repo)

    if not container.settings.reconciliation_enabled:
        log.log(
            event="reconciliation_disabled",
            message=f"phase {int(container.settings.phase)} < STAGING; reconciliation not run",
            level=LogLevel.WARNING,
        )
        return None

    job_repo = JobRepository(container.store)
    started = datetime.now(UTC)
    job = JobRecord(
        id=job_id(_JOB_TYPE, started),
        job_type=_JOB_TYPE,
        status=JobStatus.RUNNING,
        created_at=started,
        updated_at=started,
    )
    job_repo.save(job)

    try:
        report = container.reconciliation_service.reconcile()
    except Exception as exc:
        job_repo.save(
            job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "error": str(exc),
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        log.log(
            event="reconciliation_failed",
            message=f"reconciliation job failed: {exc}",
            level=LogLevel.ERROR,
            metadata={"job_id": job.id},
        )
        raise

    job_repo.save(
        job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": datetime.now(UTC)})
    )
    return report


def main() -> None:
    report = run_reconciliation()
    if report is None:
        print("reconciliation: disabled for this phase")
        return
    print(
        f"reconciliation: in_sync={report.in_sync} "
        f"matched={len(report.matched)} discrepancies={len(report.discrepancies)}"
    )


if __name__ == "__main__":
    main()
