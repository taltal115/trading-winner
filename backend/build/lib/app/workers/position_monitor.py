"""Scheduled position-monitor worker (Phase 5).

Thin job entrypoint that runs the live exit pass over open positions. Designed to
be invoked by a scheduler (GitHub Actions / Cloud Scheduler) per ARCHITECTURE.md
section 7. It is stateless and retry-safe: the monitor only acts on OPEN
positions and uses idempotent exit orders, so re-running is always safe.

Each run is wrapped in a ``JobRecord`` (RUNNING -> SUCCEEDED/FAILED) for audit,
and the worker is gated to Phase 5+ so it cannot run before staging.

Run manually:
    python -m app.workers.position_monitor
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.dependencies import AppContainer, get_container
from app.models.entities import JobRecord, Trade
from app.models.enums import JobStatus, LogLevel
from app.repositories.repositories import JobRepository
from app.services.log_writer import LogWriter
from app.utils.ids import job_id

_JOB_TYPE = "position_monitor"


def run_position_monitor(container: AppContainer | None = None) -> list[Trade]:
    """Run one monitor pass under a tracked job. Returns closed trades."""
    container = container or get_container()
    log = LogWriter(_JOB_TYPE, container.log_repo)

    if not container.settings.position_monitoring_enabled:
        log.log(
            event="position_monitor_disabled",
            message=f"phase {int(container.settings.phase)} < STAGING; monitor not run",
            level=LogLevel.WARNING,
        )
        return []

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
        closed = container.position_monitor_service.monitor_positions()
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
            event="position_monitor_failed",
            message=f"monitor job failed: {exc}",
            level=LogLevel.ERROR,
            metadata={"job_id": job.id},
        )
        raise

    job_repo.save(
        job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": datetime.now(UTC)})
    )
    return closed


def main() -> None:
    closed = run_position_monitor()
    print(f"position_monitor: closed {len(closed)} position(s)")


if __name__ == "__main__":
    main()
