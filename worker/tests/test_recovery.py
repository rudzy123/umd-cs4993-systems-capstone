"""Lease recovery for crashed workers."""

from datetime import timedelta
from uuid import UUID

import pytest
from conftest import insert_job
from sqlalchemy.orm import Session

from northstar.clock import utcnow
from northstar.models import Job
from northstar.services.queue import claim_next_job, recover_expired_leases

pytestmark = pytest.mark.usefixtures("clean_tables")


def _load(session_factory, job_id: str) -> Job:
    session: Session = session_factory()
    try:
        job = session.get(Job, UUID(job_id))
        assert job is not None
        session.expunge(job)
        return job
    finally:
        session.close()


def _expire(session_factory, job_id: str) -> None:
    session: Session = session_factory()
    try:
        with session.begin():
            job = session.get(Job, UUID(job_id))
            assert job is not None
            job.lease_expires_at = utcnow() - timedelta(seconds=5)
    finally:
        session.close()


def test_expired_lease_requeues_when_retries_remain(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings, max_retries=2)
    assert claim_next_job(session_factory, "worker-crashed", settings) is not None
    _expire(session_factory, job_id)
    assert recover_expired_leases(session_factory) == 1
    job = _load(session_factory, job_id)
    assert job.status == "retrying"
    assert job.retry_count == 1
    assert job.worker_id is None
    assert job.lease_expires_at is None
    assert "retried" in (job.error_summary or "")


def test_expired_lease_fails_when_retries_are_spent(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings, max_retries=0)
    assert claim_next_job(session_factory, "worker-crashed", settings) is not None
    _expire(session_factory, job_id)
    assert recover_expired_leases(session_factory) == 1
    job = _load(session_factory, job_id)
    assert job.status == "failed"
    assert job.retry_count == 0
    assert job.finished_at is not None
    assert "no retries remaining" in (job.error_summary or "")


def test_fresh_lease_is_not_recovered(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings)
    assert claim_next_job(session_factory, "worker-live", settings) is not None
    assert recover_expired_leases(session_factory) == 0
    assert _load(session_factory, job_id).status == "running"
