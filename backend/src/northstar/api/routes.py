"""HTTP routes for Northstar Job Lab."""

import logging
import re
import uuid
from typing import Any, cast

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from northstar.api.errors import ApiError
from northstar.api.schemas import HealthResponse, JobListResponse, JobResponse, to_job_response
from northstar.domain.errors import IdempotencyConflict, InputValidationError
from northstar.services import jobs as job_service

router = APIRouter()
logger = logging.getLogger("northstar.api")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_type: str = Field(pattern=r"^(sort|shortest_path|word_frequency|fibonacci)$")
    input: dict[str, Any]


def _sessions(request: Request) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], request.app.state.session_factory)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("readiness_failed", extra={"ns_exception_type": type(exc).__name__})
        raise ApiError(503, "not_ready", "Database is not reachable.") from None
    return HealthResponse(status="ready")


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(
    body: CreateJobRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None),
) -> JobResponse:
    if idempotency_key is not None and _IDEMPOTENCY.fullmatch(idempotency_key) is None:
        raise ApiError(
            422,
            "validation_error",
            "The request is invalid.",
            [
                {
                    "loc": ["header", "Idempotency-Key"],
                    "message": "Use 1-128 letters, numbers, underscores, or hyphens.",
                }
            ],
        )
    session = _sessions(request)()
    try:
        try:
            job, outcome = job_service.create_job(
                session,
                job_type=body.job_type,
                raw_input=body.input,
                idempotency_key=idempotency_key,
                max_retries=request.app.state.settings.max_retries,
            )
        except InputValidationError as exc:
            raise ApiError(422, "validation_error", "The request is invalid.", exc.details) from exc
        except IdempotencyConflict as exc:
            raise ApiError(
                409,
                "idempotency_conflict",
                "This Idempotency-Key was already used for a different request.",
            ) from exc
        payload = to_job_response(job)
    finally:
        session.close()
    if outcome == "replayed":
        response.status_code = 200
    return payload


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> JobListResponse:
    session = _sessions(request)()
    try:
        jobs = job_service.list_jobs(session, limit=limit, offset=offset)
        return JobListResponse(
            jobs=[to_job_response(job) for job in jobs],
            limit=limit,
            offset=offset,
        )
    finally:
        session.close()


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, request: Request) -> JobResponse:
    session = _sessions(request)()
    try:
        job = job_service.get_job(session, job_id)
        if job is None:
            raise ApiError(404, "not_found", "Job not found.")
        return to_job_response(job)
    finally:
        session.close()


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: uuid.UUID, request: Request) -> JobResponse:
    session = _sessions(request)()
    try:
        job, outcome = job_service.cancel_job(session, job_id)
        if job is None or outcome == "not_found":
            raise ApiError(404, "not_found", "Job not found.")
        if outcome == "conflict":
            raise ApiError(
                409,
                "conflict",
                "Only queued or retrying jobs can be cancelled.",
                [{"loc": ["status"], "message": job.status}],
            )
        return to_job_response(job)
    finally:
        session.close()
