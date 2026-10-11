FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NORTHSTAR_MIGRATIONS_DIR=/app/database/migrations \
    NORTHSTAR_HEARTBEAT_PATH=/tmp/northstar-worker-heartbeat

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin northstar

COPY backend/pyproject.toml backend/README.md /app/backend/
COPY backend/src /app/backend/src
COPY worker/pyproject.toml worker/README.md /app/worker/
COPY worker/src /app/worker/src
COPY database/migrations /app/database/migrations

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/backend \
    && pip install --no-cache-dir --no-deps /app/worker

USER northstar

HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import pathlib,time; p=pathlib.Path('/tmp/northstar-worker-heartbeat'); raise SystemExit(0 if p.exists() and time.time()-p.stat().st_mtime<30 else 1)"

CMD ["python", "-m", "northstar_worker"]
