# Backend image for the AI Trading System (FastAPI).
# Build context is the backend/ directory:
#   docker build -t trading-winner-backend backend/
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package with the Firestore backend (prod uses firestore).
# Copy the build inputs first so the dependency layer caches across code edits.
COPY pyproject.toml ./
COPY app ./app
RUN pip install ".[firestore]"

# Run as a non-root user (least privilege; execution engine isolated).
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Cloud Run injects PORT=8080; local ``docker run`` defaults to 8000.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD sh -c 'python -c "import os,urllib.request,sys; p=os.environ.get(\"PORT\",\"8000\"); sys.exit(0 if urllib.request.urlopen(f\"http://localhost:{p}/health\").status==200 else 1)"'

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
