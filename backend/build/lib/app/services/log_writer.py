"""Structured logging to the Firestore ``logs/`` collection.

CODING_STANDARDS.md 9/13: never fail silently; every important operation logs
to ``logs/`` with a structured, traceable payload.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entities import LogEntry
from app.models.enums import LogLevel
from app.repositories.repositories import LogRepository
from app.utils.ids import log_id


class LogWriter:
    def __init__(self, service: str, log_repo: LogRepository) -> None:
        self._service = service
        self._repo = log_repo
        self._sequence = 0

    def log(
        self,
        event: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        metadata: dict[str, object] | None = None,
    ) -> LogEntry:
        self._sequence += 1
        now = datetime.now(UTC)
        entry = LogEntry(
            id=log_id(self._service, now, self._sequence),
            service=self._service,
            level=level,
            event=event,
            message=message,
            timestamp=now,
            metadata=metadata or {},
        )
        return self._repo.save(entry)
