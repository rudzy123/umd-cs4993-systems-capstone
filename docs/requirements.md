# Requirements

## Problem

Northstar Job Lab accepts a small computational job, stores it durably, executes it in a separate process, and shows the outcome. The system is a teaching instrument for algorithms, operating systems, networking, databases, security, software engineering, and interface design.

## Users

The only user is a person on the same machine, using a browser or an HTTP client. There are no accounts, roles, or tenants.

## Functional requirements

| ID | Requirement | How it is met |
| --- | --- | --- |
| FR-1 | Submit a supported job | `POST /jobs` with `job_type` and `input` |
| FR-2 | Receive a job identifier | Response field `id`, a UUID |
| FR-3 | Retrieve job status | `GET /jobs/{id}` |
| FR-4 | List recent jobs | `GET /jobs?limit=20` (limit 1–100) |
| FR-5 | Retrieve completed results | `result` on a succeeded job |
| FR-6 | Display validation errors | HTTP 422 body `error.details` |
| FR-7 | Distinguish queued, running, succeeded, failed, and retrying | `status` plus the cancelled state |
| FR-8 | Cancel a queued job safely | `POST /jobs/{id}/cancel` from `queued` or `retrying` only |
| FR-9 | Preserve a user-safe failure | `error_summary` is at most 400 characters and does not include a traceback |

Supported job types are `sort`, `shortest_path`, `word_frequency`, and `fibonacci`.

## Job states

```text
queued    -> running | cancelled
retrying  -> running | cancelled
running   -> succeeded | retrying | failed
succeeded, failed, cancelled -> terminal
```

A second cancel, or a cancel of a running or terminal job, returns HTTP 409.

## API

| Method | Path | Success | Notes |
| --- | --- | --- | --- |
| POST | `/jobs` | 201, or 200 when an idempotency key replays | Body is strictly validated |
| GET | `/jobs` | 200 | Newest first |
| GET | `/jobs/{id}` | 200 | 404 when missing |
| POST | `/jobs/{id}/cancel` | 200 | 409 when the state cannot be cancelled |
| GET | `/health` | 200 | Process is up |
| GET | `/ready` | 200 or 503 | Database answers `SELECT 1` |

Error bodies use one shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request is invalid.",
    "details": [{ "loc": ["input", "n"], "message": "Input should be greater than or equal to 0" }]
  }
}
```

Codes include `validation_error`, `not_found`, `conflict`, `payload_too_large`, `not_ready`, and `internal_error`. HTTP 500 uses a fixed message and does not echo the exception.

`Idempotency-Key` is optional. It must match `[A-Za-z0-9_-]{1,128}`. The server stores a SHA-256 fingerprint of the canonical job type and input. The key is not returned in job responses.

## Input limits

| Job | Limit |
| --- | --- |
| Request body | 1,048,576 bytes by `Content-Length` |
| Sort | 10,000 finite numbers, absolute value at most 1e15, booleans rejected |
| Shortest path | 300 unique node ids, 2,000 edges, weights from 0 through 1e9 |
| Word frequency | 100,000 characters, `top_n` from 1 through 100, default 20 |
| Fibonacci | integer `n` from 0 through 10,000 |

Extra JSON fields are rejected.

## Non-functional requirements

- Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, pytest, Ruff, and mypy.
- A separate worker process with bounded polling, graceful shutdown, safe claiming, a retry limit, and a failure state.
- No Redis and no cloud services.
- React, TypeScript, Vite, semantic HTML, Vitest, and React Testing Library.
- Docker Compose, GitHub Actions, a Makefile, environment variables, and health checks.
- Secrets are configuration, not committed files. `.env.example` holds local defaults only.

## Out of scope

Authentication, multi-tenant isolation, distributed tracing, horizontal autoscaling, and jobs other than the four listed types.
