"""Shared fixtures for PostgreSQL-backed tests."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from northstar.api.app import create_app
from northstar.config import Settings
from northstar.db import make_engine, make_session_factory
from northstar.migrate import apply_migrations, resolve_migrations_dir
from northstar.services.jobs import create_job

_DB_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _database_url() -> str:
    return os.environ.get(
        "NORTHSTAR_TEST_DATABASE_URL",
        "postgresql+psycopg://northstar:northstar@127.0.0.1:5432/northstar_test",
    )


def _admin_engine(url: str) -> Engine:
    admin_url = make_url(url).set(database="postgres")
    return create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)


def ensure_database(url: str) -> None:
    database = make_url(url).database
    if database is None or _DB_NAME.fullmatch(database) is None:
        raise RuntimeError("Refusing to create a database with an unexpected name.")
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        engine = _admin_engine(url)
        try:
            with engine.connect() as connection:
                exists = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database},
                ).scalar()
                if exists is None:
                    connection.execute(text(f'CREATE DATABASE "{database}"'))
            return
        except Exception as exc:  # noqa: BLE001 - retry while postgres starts
            last_error = exc
            time.sleep(0.5)
        finally:
            engine.dispose()
    raise RuntimeError("PostgreSQL is not ready for tests.") from last_error


def recreate_database(url: str, name: str) -> None:
    if _DB_NAME.fullmatch(name) is None:
        raise RuntimeError("Refusing to recreate a database with an unexpected name.")
    engine = _admin_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    return _database_url()


@pytest.fixture(scope="session")
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        cors_origins="http://localhost:5173",
        max_retries=2,
        lease_seconds=30,
        poll_interval_seconds=0.2,
        log_level="WARNING",
        max_body_bytes=2048,
        database_wait_seconds=5,
        worker_id="test-worker",
    )


@pytest.fixture(scope="session")
def engine(database_url: str, settings: Settings) -> Iterator[Engine]:
    ensure_database(database_url)
    database_engine = make_engine(database_url)
    apply_migrations(database_engine, resolve_migrations_dir(settings))
    yield database_engine
    database_engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture(scope="session")
def app(settings: Settings, engine: Engine):
    del engine
    application = create_app(settings)
    yield application


@pytest.fixture(scope="session")
def client(app) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def clean_tables(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE job_events, job_attempts, jobs RESTART IDENTITY CASCADE")
        )
    yield


def insert_job(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    job_type: str = "sort",
    raw_input: dict[str, object] | None = None,
    max_retries: int | None = None,
) -> str:
    payload = {"numbers": [3, 1, 2]} if raw_input is None else raw_input
    session = session_factory()
    try:
        job, _outcome = create_job(
            session,
            job_type=job_type,
            raw_input=payload,
            idempotency_key=None,
            max_retries=settings.max_retries if max_retries is None else max_retries,
        )
        return str(job.id)
    finally:
        session.close()


def utcnow() -> datetime:
    return datetime.now(UTC)
