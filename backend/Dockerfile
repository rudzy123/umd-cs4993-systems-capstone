FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NORTHSTAR_MIGRATIONS_DIR=/app/database/migrations

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin northstar

COPY backend/pyproject.toml backend/README.md /app/backend/
COPY backend/src /app/backend/src
COPY database/migrations /app/database/migrations

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/backend

USER northstar

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready')"

CMD ["uvicorn", "northstar.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
