"""Schema migration and database invariants."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from conftest import recreate_database
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from northstar.config import Settings
from northstar.db import make_engine
from northstar.migrate import apply_migrations, resolve_migrations_dir


def test_migrations_apply_once_and_enforce_invariants(database_url: str) -> None:
    name = "northstar_migration_test"
    recreate_database(database_url, name)
    url = make_url(database_url).set(database=name).render_as_string(hide_password=False)
    settings = Settings(database_url=url)
    engine = make_engine(url)
    try:
        first = apply_migrations(engine, resolve_migrations_dir(settings))
        second = apply_migrations(engine, resolve_migrations_dir(settings))
        assert first == ["001_initial.sql", "002_status_updated_index.sql"]
        assert second == []
        job_id = uuid4()
        now = datetime.now(UTC)
        with engine.begin() as connection:
            index = connection.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = 'jobs_status_updated_idx'")
            ).scalar()
            assert index == 1
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, job_type, status, input_payload, retry_count, max_retries,
                        version, created_at, updated_at
                    ) VALUES (
                        :id, 'sort', 'queued', CAST(:payload AS jsonb), 0, 2,
                        1, :now, :now
                    )
                    """
                ),
                {"id": job_id, "payload": '{"numbers": [1]}', "now": now},
            )
        with (
            pytest.raises(SQLAlchemyError, match="invalid job status transition"),
            engine.begin() as connection,
        ):
            connection.execute(
                text("UPDATE jobs SET status = 'succeeded' WHERE id = :id"),
                {"id": job_id},
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE jobs
                    SET status = 'running', worker_id = 'worker-db', started_at = :now
                    WHERE id = :id
                    """
                ),
                {"id": job_id, "now": datetime.now(UTC)},
            )
        with (
            pytest.raises(SQLAlchemyError, match="jobs_result_matches_status"),
            engine.begin() as connection,
        ):
            connection.execute(
                text(
                    """
                    UPDATE jobs
                    SET status = 'succeeded', finished_at = :now
                    WHERE id = :id
                    """
                ),
                {"id": job_id, "now": datetime.now(UTC)},
            )
    finally:
        engine.dispose()
