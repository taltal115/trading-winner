"""Scheduled daily-pipeline worker (ARCHITECTURE.md section 7).

Thin job entrypoint that runs the full daily pipeline (ingest -> features ->
signals -> phase-gated AI/risk/execution). Wrapping ``run_daily`` in a tracked
``JobRecord`` gives scheduled runs the same audit trail as the other workers.
The pipeline itself is idempotent (deterministic ids + execution gates), so
re-running a schedule is safe.

Run manually:
    python -m app.workers.daily_pipeline
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.dependencies import AppContainer, get_container
from app.models.entities import JobRecord, Signal
from app.models.enums import JobStatus, LogLevel
from app.repositories.repositories import JobRepository
from app.services.log_writer import LogWriter
from app.utils.ids import job_id

_JOB_TYPE = "daily_pipeline"


def run_daily_pipeline(container: AppContainer | None = None) -> list[Signal]:
    """Run one daily pipeline pass under a tracked job. Returns the signals."""
    container = container or get_container()
    log = LogWriter(_JOB_TYPE, container.log_repo)

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
        signals = container.pipeline_service.run_daily()
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
            event="daily_pipeline_failed",
            message=f"daily pipeline job failed: {exc}",
            level=LogLevel.ERROR,
            metadata={"job_id": job.id},
        )
        raise

    job_repo.save(
        job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": datetime.now(UTC)})
    )
    return signals


def main() -> None:
    signals = run_daily_pipeline()
    print(f"daily_pipeline: produced {len(signals)} signal(s)")


if __name__ == "__main__":
    main()
