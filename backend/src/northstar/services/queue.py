"""Transactional claim, execution, and lease recovery."""

import copy
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from northstar.algorithms.registry import run_job
from northstar.clock import utcnow
from northstar.config import Settings
from northstar.domain.errors import InputValidationError, JobExecutionError
from northstar.domain.messages import safe_summary
from northstar.domain.status import AttemptStatus, JobStatus
from northstar.logging_config import log_event
from northstar.models import Job, JobAttempt, JobEvent

logger = logging.getLogger("northstar.queue")

GENERIC_FAILURE = "The job could not be completed. Please submit it again."
LEASE_RETRY = "The previous attempt stopped before it finished. The job will be retried."
LEASE_FINAL = "The job stopped before it finished and has no retries remaining."


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    job_type: str
    input_payload: dict[str, Any]
    version: int
    attempt_id: uuid.UUID
    attempt_number: int
    worker_id: str


def claim_next_job(
    session_factory: sessionmaker[Session],
    worker_id: str,
    settings: Settings,
) -> ClaimedJob | None:
    """Lock one claimable job and mark it running.

    The transaction commits before the caller runs the algorithm so the row
    lock is not held during computation.
    """

    session = session_factory()
    claimed: ClaimedJob | None = None
    try:
        with session.begin():
            statement = (
                select(Job)
                .where(Job.status.in_(tuple(JobStatus.CLAIMABLE)))
                .order_by(Job.created_at.asc(), Job.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = session.scalars(statement).first()
            if job is None:
                return None
            previous = job.status
            now = utcnow()
            job.status = JobStatus.RUNNING
            job.worker_id = worker_id
            job.version += 1
            job.updated_at = now
            job.error_summary = None
            job.finished_at = None
            job.lease_expires_at = now + timedelta(seconds=settings.lease_seconds)
            if job.started_at is None:
                job.started_at = now
            attempt_number = job.retry_count + 1
            attempt = JobAttempt(
                id=uuid.uuid4(),
                job_id=job.id,
                attempt_number=attempt_number,
                worker_id=worker_id,
                status=AttemptStatus.RUNNING,
                error_summary=None,
                started_at=now,
                finished_at=None,
            )
            session.add(attempt)
            session.add(
                JobEvent(
                    job_id=job.id,
                    from_status=previous,
                    to_status=JobStatus.RUNNING,
                    reason="claimed",
                    worker_id=worker_id,
                    created_at=now,
                )
            )
            session.flush()
            payload = _copy_payload(job.input_payload)
            claimed = ClaimedJob(
                id=job.id,
                job_type=job.job_type,
                input_payload=payload,
                version=job.version,
                attempt_id=attempt.id,
                attempt_number=attempt_number,
                worker_id=worker_id,
            )
    finally:
        session.close()
    if claimed is not None:
        log_event(
            logger,
            "job_claimed",
            job_id=str(claimed.id),
            worker_id=worker_id,
            attempt_number=claimed.attempt_number,
        )
    return claimed


def execute_claimed_job(session_factory: sessionmaker[Session], claimed: ClaimedJob) -> None:
    try:
        result = run_job(claimed.job_type, claimed.input_payload)
    except (JobExecutionError, InputValidationError) as exc:
        message = (
            safe_summary(str(exc))
            if isinstance(exc, JobExecutionError)
            else "Stored input failed validation and cannot be executed."
        )
        _finish_failure(
            session_factory,
            claimed,
            message=message,
            retryable=False,
            reason="permanent_failure",
        )
        return
    except Exception as exc:
        logger.error(
            "job_execution_error",
            extra={"ns_job_id": str(claimed.id), "ns_exception_type": type(exc).__name__},
        )
        _finish_failure(
            session_factory,
            claimed,
            message=GENERIC_FAILURE,
            retryable=True,
            reason="retryable_failure",
        )
        return
    _finish_success(session_factory, claimed, result)


def recover_expired_leases(session_factory: sessionmaker[Session]) -> int:
    """Requeue or fail jobs whose worker lease expired."""

    session = session_factory()
    recovered = 0
    try:
        with session.begin():
            now = utcnow()
            statement = (
                select(Job)
                .where(
                    Job.status == JobStatus.RUNNING,
                    Job.lease_expires_at.is_not(None),
                    Job.lease_expires_at < now,
                )
                .with_for_update(skip_locked=True)
            )
            jobs = list(session.scalars(statement).all())
            for job in jobs:
                _close_open_attempts(
                    session,
                    job.id,
                    "Attempt ended because the worker lease expired.",
                    now,
                )
                previous = job.status
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.RETRYING
                    job.error_summary = LEASE_RETRY
                    job.finished_at = None
                    target = JobStatus.RETRYING
                else:
                    job.status = JobStatus.FAILED
                    job.error_summary = LEASE_FINAL
                    job.finished_at = now
                    target = JobStatus.FAILED
                job.worker_id = None
                job.lease_expires_at = None
                job.updated_at = now
                job.version += 1
                session.add(
                    JobEvent(
                        job_id=job.id,
                        from_status=previous,
                        to_status=target,
                        reason="lease_expired",
                        worker_id=None,
                        created_at=now,
                    )
                )
                recovered += 1
                log_event(
                    logger,
                    "lease_expired",
                    job_id=str(job.id),
                    status=target,
                    retry_count=job.retry_count,
                )
    finally:
        session.close()
    return recovered


def _finish_success(
    session_factory: sessionmaker[Session],
    claimed: ClaimedJob,
    result: dict[str, Any],
) -> bool:
    session = session_factory()
    try:
        with session.begin():
            job = _lock_job(session, claimed.id)
            if job is None or not _owns(job, claimed):
                _record_lost(session, job, claimed)
                return False
            now = utcnow()
            job.status = JobStatus.SUCCEEDED
            job.result_payload = result
            job.error_summary = None
            job.finished_at = now
            job.updated_at = now
            job.lease_expires_at = None
            job.version += 1
            _complete_attempt(session, claimed.attempt_id, AttemptStatus.SUCCEEDED, None, now)
            session.add(
                JobEvent(
                    job_id=job.id,
                    from_status=JobStatus.RUNNING,
                    to_status=JobStatus.SUCCEEDED,
                    reason="completed",
                    worker_id=job.worker_id,
                    created_at=now,
                )
            )
    finally:
        session.close()
    log_event(logger, "job_succeeded", job_id=str(claimed.id))
    return True


def _finish_failure(
    session_factory: sessionmaker[Session],
    claimed: ClaimedJob,
    *,
    message: str,
    retryable: bool,
    reason: str,
) -> bool:
    session = session_factory()
    final_status = JobStatus.FAILED
    try:
        with session.begin():
            job = _lock_job(session, claimed.id)
            if job is None or not _owns(job, claimed):
                _record_lost(session, job, claimed)
                return False
            now = utcnow()
            summary = safe_summary(message)
            _complete_attempt(session, claimed.attempt_id, AttemptStatus.FAILED, summary, now)
            if retryable and job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.RETRYING
                job.error_summary = summary
                job.finished_at = None
                final_status = JobStatus.RETRYING
                event_reason = reason
            else:
                job.status = JobStatus.FAILED
                job.error_summary = summary
                job.finished_at = now
                final_status = JobStatus.FAILED
                event_reason = "permanent_failure" if not retryable else "retries_exhausted"
            job.worker_id = None
            job.lease_expires_at = None
            job.updated_at = now
            job.version += 1
            session.add(
                JobEvent(
                    job_id=job.id,
                    from_status=JobStatus.RUNNING,
                    to_status=final_status,
                    reason=event_reason,
                    worker_id=None,
                    created_at=now,
                )
            )
    finally:
        session.close()
    log_event(logger, "job_failed_attempt", job_id=str(claimed.id), status=final_status)
    return True


def _owns(job: Job, claimed: ClaimedJob) -> bool:
    return (
        job.status == JobStatus.RUNNING
        and job.version == claimed.version
        and job.worker_id == claimed.worker_id
    )


def _lock_job(session: Session, job_id: uuid.UUID) -> Job | None:
    return session.scalars(select(Job).where(Job.id == job_id).with_for_update()).first()


def _complete_attempt(
    session: Session,
    attempt_id: uuid.UUID,
    status: str,
    error_summary: str | None,
    finished_at: datetime,
) -> None:
    attempt = session.get(JobAttempt, attempt_id)
    if attempt is None or attempt.status != AttemptStatus.RUNNING:
        return
    attempt.status = status
    attempt.error_summary = error_summary
    attempt.finished_at = finished_at


def _close_open_attempts(
    session: Session, job_id: uuid.UUID, message: str, finished_at: datetime
) -> None:
    statement = select(JobAttempt).where(
        JobAttempt.job_id == job_id,
        JobAttempt.status == AttemptStatus.RUNNING,
    )
    for attempt in session.scalars(statement).all():
        attempt.status = AttemptStatus.FAILED
        attempt.error_summary = safe_summary(message)
        attempt.finished_at = finished_at


def _record_lost(session: Session, job: Job | None, claimed: ClaimedJob) -> None:
    if job is None:
        return
    session.add(
        JobEvent(
            job_id=job.id,
            from_status=job.status,
            to_status=job.status,
            reason="ownership_lost",
            worker_id=None,
            created_at=utcnow(),
        )
    )
    log_event(logger, "ownership_lost", job_id=str(claimed.id), status=job.status)


def _copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    copied = copy.deepcopy(payload)
    if not isinstance(copied, dict):
        return {}
    return copied
