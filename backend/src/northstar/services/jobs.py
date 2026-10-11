"""Create, read, and cancel jobs."""

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from northstar.clock import utcnow
from northstar.domain.errors import IdempotencyConflict
from northstar.domain.inputs import canonical_payload, parse_job_input
from northstar.domain.status import JobStatus
from northstar.logging_config import log_event
from northstar.models import Job, JobEvent

logger = logging.getLogger("northstar.jobs")


def fingerprint_for(job_type: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"job_type": job_type, "input": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def create_job(
    session: Session,
    *,
    job_type: str,
    raw_input: dict[str, Any],
    idempotency_key: str | None,
    max_retries: int,
) -> tuple[Job, str]:
    parsed = parse_job_input(job_type, raw_input)
    payload = canonical_payload(parsed)
    fingerprint = fingerprint_for(job_type, payload) if idempotency_key else None
    created: Job | None = None
    replayed: Job | None = None

    try:
        with session.begin():
            existing = _find_idempotent(session, idempotency_key)
            if existing is not None:
                if existing.idempotency_fingerprint != fingerprint:
                    raise IdempotencyConflict()
                replayed = existing
            else:
                now = utcnow()
                job = Job(
                    id=uuid.uuid4(),
                    job_type=job_type,
                    status=JobStatus.QUEUED,
                    input_payload=payload,
                    result_payload=None,
                    error_summary=None,
                    retry_count=0,
                    max_retries=max_retries,
                    version=1,
                    worker_id=None,
                    idempotency_key=idempotency_key,
                    idempotency_fingerprint=fingerprint,
                    created_at=now,
                    updated_at=now,
                    started_at=None,
                    finished_at=None,
                    lease_expires_at=None,
                )
                session.add(job)
                session.add(
                    JobEvent(
                        job_id=job.id,
                        from_status=None,
                        to_status=JobStatus.QUEUED,
                        reason="accepted",
                        worker_id=None,
                        created_at=now,
                    )
                )
                created = job
    except IntegrityError:
        session.rollback()
        with session.begin():
            existing = _find_idempotent(session, idempotency_key)
        if existing is None or idempotency_key is None:
            raise
        if existing.idempotency_fingerprint != fingerprint:
            raise IdempotencyConflict() from None
        return existing, "replayed"

    if replayed is not None:
        return replayed, "replayed"
    if created is None:
        raise RuntimeError("job was not stored")
    log_event(logger, "job_accepted", job_id=str(created.id), job_type=created.job_type)
    return created, "created"


def get_job(session: Session, job_id: uuid.UUID) -> Job | None:
    return session.get(Job, job_id)


def list_jobs(session: Session, *, limit: int, offset: int) -> list[Job]:
    statement = (
        select(Job).order_by(Job.created_at.desc(), Job.id.desc()).limit(limit).offset(offset)
    )
    return list(session.scalars(statement).all())


def cancel_job(session: Session, job_id: uuid.UUID) -> tuple[Job | None, str]:
    job: Job | None = None
    outcome = "not_found"
    with session.begin():
        job = session.scalars(select(Job).where(Job.id == job_id).with_for_update()).first()
        if job is None:
            outcome = "not_found"
        elif job.status not in JobStatus.CLAIMABLE:
            outcome = "conflict"
        else:
            previous = job.status
            now = utcnow()
            job.status = JobStatus.CANCELLED
            job.error_summary = "Cancelled by user."
            job.finished_at = now
            job.updated_at = now
            job.worker_id = None
            job.lease_expires_at = None
            job.version += 1
            session.add(
                JobEvent(
                    job_id=job.id,
                    from_status=previous,
                    to_status=JobStatus.CANCELLED,
                    reason="cancelled",
                    worker_id=None,
                    created_at=now,
                )
            )
            outcome = "cancelled"
    if job is not None and outcome == "cancelled":
        log_event(logger, "job_cancelled", job_id=str(job.id), status=job.status)
    return job, outcome


def _find_idempotent(session: Session, idempotency_key: str | None) -> Job | None:
    if idempotency_key is None:
        return None
    return session.scalars(select(Job).where(Job.idempotency_key == idempotency_key)).first()
