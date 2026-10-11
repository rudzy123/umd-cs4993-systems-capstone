"""Execution outcomes: success, permanent failure, and retry."""

from uuid import UUID

import pytest
from conftest import insert_job
from sqlalchemy import select
from sqlalchemy.orm import Session

from northstar.algorithms.registry import run_job
from northstar.models import Job, JobAttempt
from northstar.services.queue import execute_claimed_job
from northstar_worker.loop import process_once

pytestmark = pytest.mark.usefixtures("clean_tables")


def _job(session_factory, job_id: str) -> Job:
    session: Session = session_factory()
    try:
        job = session.get(Job, UUID(job_id))
        assert job is not None
        session.expunge(job)
        return job
    finally:
        session.close()


def _attempts(session_factory, job_id: str) -> list[JobAttempt]:
    session: Session = session_factory()
    try:
        rows = list(
            session.scalars(
                select(JobAttempt)
                .where(JobAttempt.job_id == UUID(job_id))
                .order_by(JobAttempt.attempt_number)
            ).all()
        )
        for row in rows:
            session.expunge(row)
        return rows
    finally:
        session.close()


def test_successful_sort(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings, raw_input={"numbers": [3, 1, 2]})
    assert process_once(session_factory, settings, "worker-success") is True
    job = _job(session_factory, job_id)
    assert job.status == "succeeded"
    assert job.result_payload is not None
    assert job.result_payload["sorted"] == [1, 2, 3]
    attempts = _attempts(session_factory, job_id)
    assert len(attempts) == 1
    assert attempts[0].status == "succeeded"


def test_corrupt_payload_fails_without_retry(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings)
    session = session_factory()
    try:
        with session.begin():
            job = session.get(Job, UUID(job_id))
            assert job is not None
            job.input_payload = {"numbers": "nope"}
    finally:
        session.close()
    assert process_once(session_factory, settings, "worker-bad") is True
    job = _job(session_factory, job_id)
    assert job.status == "failed"
    assert job.retry_count == 0
    assert job.error_summary == "Stored input failed validation and cannot be executed."
    assert "nope" not in (job.error_summary or "")


def test_retry_then_success(session_factory, settings, monkeypatch) -> None:
    calls = {"count": 0}

    def flaky(job_type: str, payload: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("disk-offline")
        return run_job(job_type, payload)  # type: ignore[arg-type]

    monkeypatch.setattr("northstar.services.queue.run_job", flaky)
    job_id = insert_job(session_factory, settings, max_retries=1)
    assert process_once(session_factory, settings, "worker-retry") is True
    waiting = _job(session_factory, job_id)
    assert waiting.status == "retrying"
    assert waiting.retry_count == 1
    assert "disk-offline" not in (waiting.error_summary or "")
    assert process_once(session_factory, settings, "worker-retry") is True
    done = _job(session_factory, job_id)
    assert done.status == "succeeded"
    assert [item.status for item in _attempts(session_factory, job_id)] == ["failed", "succeeded"]


def test_retries_exhausted(session_factory, settings, monkeypatch) -> None:
    def always_fail(_job_type: str, _payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("secret-internal-disk")

    monkeypatch.setattr("northstar.services.queue.run_job", always_fail)
    job_id = insert_job(session_factory, settings, max_retries=1)
    assert process_once(session_factory, settings, "worker-fail") is True
    assert process_once(session_factory, settings, "worker-fail") is True
    job = _job(session_factory, job_id)
    assert job.status == "failed"
    assert job.retry_count == 1
    assert job.error_summary == "The job could not be completed. Please submit it again."
    assert "secret-internal-disk" not in (job.error_summary or "")
    assert "Traceback" not in (job.error_summary or "")


def test_stale_worker_cannot_overwrite_recovered_job(session_factory, settings) -> None:
    from datetime import timedelta

    from northstar.clock import utcnow
    from northstar.services.queue import claim_next_job, recover_expired_leases

    job_id = insert_job(session_factory, settings)
    claimed = claim_next_job(session_factory, "worker-old", settings)
    assert claimed is not None
    session = session_factory()
    try:
        with session.begin():
            job = session.get(Job, UUID(job_id))
            assert job is not None
            job.lease_expires_at = utcnow() - timedelta(seconds=5)
    finally:
        session.close()
    assert recover_expired_leases(session_factory) == 1
    execute_claimed_job(session_factory, claimed)
    job = _job(session_factory, job_id)
    assert job.status == "retrying"
    assert job.result_payload is None
