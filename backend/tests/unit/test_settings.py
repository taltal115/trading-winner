"""Settings edge cases (CI env vars, empty strings)."""

import app.config.settings as settings_module
from app.config.settings import Settings, SystemPhase


def test_empty_tw_phase_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("TW_PHASE", "")
    settings_module._settings = None
    assert Settings().phase == SystemPhase.MVP_READ_ONLY


def test_empty_firestore_project_env_is_none(monkeypatch) -> None:
    monkeypatch.setenv("TW_FIRESTORE_PROJECT", "")
    settings_module._settings = None
    assert Settings().firestore_project is None


def test_valid_tw_phase_env_is_parsed(monkeypatch) -> None:
    monkeypatch.setenv("TW_PHASE", "5")
    settings_module._settings = None
    assert Settings().phase == SystemPhase.STAGING
