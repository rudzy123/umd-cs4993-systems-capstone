"""API response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from northstar.models import Job, JobAttempt


class AttemptResponse(BaseModel):
    attempt_number: int
    status: str
    worker_id: str
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class JobResponse(BaseModel):
    id: UUID
    job_type: str
    status: str
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    error_summary: str | None = None
    retry_count: int
    max_retries: int
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: list[AttemptResponse] = Field(default_factory=list)


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str


def to_job_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        input=dict(job.input_payload),
        result=None if job.result_payload is None else dict(job.result_payload),
        error_summary=job.error_summary,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        version=job.version,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        attempts=[_attempt(item) for item in job.attempts],
    )


def _attempt(item: JobAttempt) -> AttemptResponse:
    return AttemptResponse(
        attempt_number=item.attempt_number,
        status=item.status,
        worker_id=item.worker_id,
        error_summary=item.error_summary,
        started_at=item.started_at,
        finished_at=item.finished_at,
    )
