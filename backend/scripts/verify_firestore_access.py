"""Pre-flight check for GitHub Actions / ops: can this identity write Firestore?

Exits 0 after a create+delete on ``_healthchecks/github_actions``. Exits 1 with
actionable stderr on auth or IAM failures (common when the service account lacks
``roles/datastore.user`` or the JSON secret is from a different project).
"""

from __future__ import annotations

import sys

from app.config.settings import get_settings
from app.repositories.firestore_store import FirestoreDocumentStore


def main() -> None:
    settings = get_settings()
    project = settings.firestore_project
    if settings.repository_backend != "firestore":
        print("verify_firestore_access: TW_REPOSITORY_BACKEND is not firestore; skip")
        return

    doc_id = "github_actions"
    collection = "_healthchecks"
    try:
        store = FirestoreDocumentStore(project)
        store.set(collection, doc_id, {"ok": True, "source": "verify_firestore_access"})
        store.delete(collection, doc_id)
    except Exception as exc:
        print(
            "Firestore access check FAILED.\n"
            f"  project: {project!r}\n"
            f"  error: {exc}\n"
            "Fix: grant the service account roles/datastore.user on this project,\n"
            "     ensure Firestore (Native mode) is created, and confirm\n"
            "     FIREBASE_SERVICE_ACCOUNT JSON is from the same project as\n"
            "     TW_FIRESTORE_PROJECT.\n"
            "See README.md → GitHub Actions scheduler (Firestore).",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(f"Firestore write OK (project={project})")


if __name__ == "__main__":
    main()
