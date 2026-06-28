from app.api.dependencies import AppContainer
from app.config.settings import Settings, SystemPhase
from app.workers.daily_pipeline import run_daily_pipeline


def test_worker_runs_pipeline_and_records_job() -> None:
    container = AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))
    signals = run_daily_pipeline(container)

    assert len(signals) >= 1
    jobs = container.store.list("jobs")
    assert any(j["job_type"] == "daily_pipeline" and j["status"] == "SUCCEEDED" for j in jobs)


def test_worker_is_idempotent_across_runs() -> None:
    container = AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))
    run_daily_pipeline(container)
    run_daily_pipeline(container)
    # Pipeline execution is idempotent: NVDA opens once despite two runs.
    assert len(container.trade_repo.list()) == 1
    # Runs are audited as succeeded daily-pipeline jobs.
    daily_jobs = [
        j
        for j in container.store.list("jobs")
        if j["job_type"] == "daily_pipeline" and j["status"] == "SUCCEEDED"
    ]
    assert len(daily_jobs) >= 1
