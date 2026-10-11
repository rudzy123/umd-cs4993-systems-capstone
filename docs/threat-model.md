# Threat model

Method: STRIDE, scoped to a local lab. The trust boundary is the host. Anyone who can open `127.0.0.1:8000`, `127.0.0.1:8080`, or `127.0.0.1:5432` is treated as a trusted operator. This document says what the lab resists and what it deliberately does not resist.

## Assets

- Job inputs and results stored in PostgreSQL.
- The database role password.
- State-transition history in `job_events`.
- Availability of the API, worker, and database on one machine.

## Actors

| Actor | Capability |
| --- | --- |
| Local operator | Submits jobs, reads results, stops processes |
| Another local process | Can reach the published localhost ports |
| A remote attacker | Out of scope unless someone publishes the ports |

## STRIDE

### Spoofing

There is no authentication. Any client that can reach the API can create, read, and cancel jobs. Compose publishes ports on `127.0.0.1` only, which stops a remote interface from binding the service by default. This is a network placement control, not an identity control.

A worker identity is a random `worker-<12 hex>` string, or `NORTHSTAR_WORKER_ID` when set. It is an ownership token inside the database, not a credential presented to clients. Completion checks that token together with the job version.

### Tampering

- Request bodies are parsed as JSON by the framework and validated by Pydantic models with `extra="forbid"`. The worker does not use `pickle` or `eval`.
- Stored payloads are checked again before execution. A row that no longer matches the schema fails permanently.
- SQL uses SQLAlchemy expressions and bound parameters. Schema changes are SQL files executed as migration text, not as user input.
- Status changes that skip the allowed graph are rejected by the `jobs_status_transition` trigger.
- A stale worker cannot overwrite a job after recovery because the completion update requires the current version and worker id.
- Idempotency replays compare a SHA-256 fingerprint of the canonical body. A reused key with a different body is a conflict, not a silent overwrite.

### Repudiation

`job_events` records the from-status, to-status, reason, worker id, and timestamp. It does not store the input or result. Application logs follow the same rule. An operator can reconstruct who claimed a job and how the state moved. The lab cannot prove which human submitted it, because there are no accounts.

### Information disclosure

- Unhandled exceptions become HTTP 500 with a fixed message. The log line records the exception class, not the message and not a traceback. Validation errors can embed user input in their message, so a traceback would leak that input.
- `/ready` logs the exception type and returns 503 without the database URL.
- CORS allows only the configured local origins, with credentials disabled and methods limited to GET, POST, and OPTIONS.
- The nginx image sets `X-Content-Type-Options`, `Referrer-Policy`, and a content security policy that keeps scripts and connections on the same origin.
- Error summaries are truncated to 400 characters. Retryable crashes use a generic sentence. Permanent validation failures use a fixed sentence that does not echo the bad payload.

### Denial of service

- Body size is limited by `Content-Length` (default 1 MiB). A chunked body without that header is not measured. That residual is accepted for the lab and documented.
- Each algorithm has a hard input bound: 10,000 numbers, 300 nodes and 2,000 edges, 100,000 characters, Fibonacci `n` at most 10,000.
- Fibonacci uses decimal strings and quadratic bit work. The cap keeps one job inside a few seconds on a laptop.
- The worker runs one job at a time and polls between 0.1 and 5 seconds. A slow job delays later jobs on that worker. Additional worker processes drain the queue concurrently.
- Database pools are small (`pool_size` 5, `max_overflow` 10) with `pool_pre_ping`.

### Elevation of privilege

The API and worker containers run as uid 10001, not root. They have no host mounts other than what Compose gives the database volume. The database role can read and write the Northstar schema. It is not a superuser in the application path. There is no shell, file upload, or job type that executes submitted code.

## Decisions

| Decision | Reason |
| --- | --- |
| Environment variables for the database URL and password | Keeps secrets out of git. `.env` is ignored. |
| Local password `northstar` as a default | The lab must start without a secret ceremony. Operators replace it before any shared host. |
| No authentication | A login system would dominate the capstone and would still be unsafe if ports were public. The honest boundary is localhost. |
| Parameterized ORM plus a status trigger | Application checks can be skipped by a bug. The trigger still rejects illegal transitions. |
| Narrow CORS | The browser is a second client, not an open cross-origin API. |

## Residual risks

- Publishing port 5432, 8000, or 8080 on a public interface exposes every job and the database.
- A local process can cancel another process's queued jobs.
- Logs on the host are readable by the operator and by anyone with access to the container output.
- The size limit does not cover chunked uploads.
- Lease recovery can run a job twice if the first worker is alive but late. The fence prevents the late worker from publishing its result. The algorithm itself may still have run twice. Jobs must tolerate that. They write only to the job row, so a repeated Fibonacci or sort has no external side effect.
