"""Concurrent claim tests."""

import threading
from uuid import UUID

import pytest
from conftest import insert_job
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from northstar.models import JobAttempt
from northstar.services.queue import claim_next_job

pytestmark = pytest.mark.usefixtures("clean_tables")


def _attempt_count(session_factory, job_id: str) -> int:
    session: Session = session_factory()
    try:
        return int(
            session.scalar(
                select(func.count())
                .select_from(JobAttempt)
                .where(JobAttempt.job_id == UUID(job_id))
            )
            or 0
        )
    finally:
        session.close()


def test_second_claim_finds_nothing_when_one_job_is_running(session_factory, settings) -> None:
    job_id = insert_job(session_factory, settings)
    first = claim_next_job(session_factory, "worker-a", settings)
    second = claim_next_job(session_factory, "worker-b", settings)
    assert first is not None
    assert str(first.id) == job_id
    assert second is None
    assert _attempt_count(session_factory, job_id) == 1


def test_two_workers_cannot_claim_the_same_job(session_factory, settings) -> None:
    for _ in range(10):
        job_id = insert_job(session_factory, settings)
        barrier = threading.Barrier(2)
        found: list[object] = []
        errors: list[BaseException] = []
        lock = threading.Lock()

        def run(
            worker_name: str,
            start: threading.Barrier = barrier,
            guard: threading.Lock = lock,
            claims: list[object] = found,
            failures: list[BaseException] = errors,
        ) -> None:
            try:
                start.wait(timeout=5)
                claimed = claim_next_job(session_factory, worker_name, settings)
                with guard:
                    claims.append(claimed)
            except BaseException as exc:  # noqa: BLE001
                failures.append(exc)

        threads = [
            threading.Thread(target=run, args=("worker-a",)),
            threading.Thread(target=run, args=("worker-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert errors == []
        claims = [item for item in found if item is not None]
        assert len(claims) == 1
        assert _attempt_count(session_factory, job_id) == 1
