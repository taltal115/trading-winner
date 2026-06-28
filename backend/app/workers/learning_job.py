"""Scheduled learning-loop worker (Phase 6, DEPLOYMENT.md 5.3).

Backfills ``outcomes/`` records for any closed trades that do not yet have a
learning outcome (e.g. trades closed before Phase 6 was enabled, or when the
monitor ran without the outcome hook). Idempotent and safe to re-run.

Run manually:
    python -m app.workers.learning_job
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.dependencies import AppContainer, get_container
from app.models.entities import JobRecord, TradeOutcome
from app.models.enums import JobStatus, LogLevel
from app.repositories.repositories import JobRepository
from app.services.log_writer import LogWriter
from app.utils.ids import job_id

_JOB_TYPE = "learning_job"


def run_learning_job(container: AppContainer | None = None) -> list[TradeOutcome] | None:
    """Process pending closed trades under a tracked job."""
    container = container or get_container()
    log = LogWriter(_JOB_TYPE, container.log_repo)

    if not container.settings.learning_loop_enabled:
        log.log(
            event="learning_job_disabled",
            message=f"phase {int(container.settings.phase)} < PRODUCTION; learning job not run",
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
        recorded = container.outcome_service.process_pending()
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
            event="learning_job_failed",
            message=f"learning job failed: {exc}",
            level=LogLevel.ERROR,
            metadata={"job_id": job.id},
        )
        raise

    job_repo.save(
        job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": datetime.now(UTC)})
    )
    return recorded


def main() -> None:
    recorded = run_learning_job()
    if recorded is None:
        print("learning_job: disabled for this phase")
        return
    print(f"learning_job: recorded {len(recorded)} outcome(s)")


if __name__ == "__main__":
    main()
