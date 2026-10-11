# Learning retrospective

This note records how the lab uses the course material and what would change if the same design had to leave a laptop.

## Algorithms

The four jobs are real course algorithms with written complexity and hard bounds, not placeholders that sleep and return `"ok"`. Merge sort is stable and reports its comparison count. Dijkstra keeps a deterministic path by sorting adjacency and refusing to replace an equal-distance predecessor. Word frequency separates tokenization from ranking so the order of equal counts does not depend on hash randomization. Fibonacci is bottom-up dynamic programming, and the interesting limit is bit complexity: F(n) has O(n) bits, so the work is O(n²) even though the loop is O(n). The value is a decimal string because a JSON number would lose low digits.

The algorithm package does not import FastAPI or SQLAlchemy. The worker calls `run_job`. That split is what makes the unit tests fast and what makes a retry safe.

## Networking

The browser and `curl` speak HTTP/JSON to a small REST surface. The frontend in Docker does not call PostgreSQL and does not embed the database URL. nginx proxies `/api/` to the API container, so the page is same-origin. Vite does the same rewrite during development. CORS is an allow-list for the cases where the page and the API are different origins, with credentials off.

Readiness is a separate route from liveness. `/health` answers even when the database is down. `/ready` runs `SELECT 1`. Compose and the smoke script wait on `/ready`.

The worker is not an HTTP service. Using the database as the queue means the data plane and the control plane are the same system, which is a networking choice as much as a storage choice: one fewer port, one fewer protocol, and no broker to discover.

## Operating systems

The worker is its own process, with its own address space and its own failure domain. Stopping it does not stop the API. `SIGTERM` and `SIGINT` set a flag. The process does not exit inside the signal handler. It finishes the current iteration, which is the usual pattern for not leaking a half-written result. `stop_grace_period` gives that iteration time to commit.

The poll loop is a bounded wait on an event, not a busy spin. One worker runs one job at a time. Concurrency across jobs is multiple processes, which is the operating-system scheduler, not a thread pool hidden inside the algorithm.

The heartbeat file is a crude supervisor signal. If the process wedges, the mtime stops moving and the container health check fails. A crashed process leaves a `running` row. The lease is the recovery mechanism for that orphan.

## Transactions

`FOR UPDATE SKIP LOCKED` is the reason two workers cannot both leave the claim function holding the same job. The lock lasts for the claim transaction only. The version and worker id are the fence for the later completion transaction. Together they cover the two gaps: the race at claim time, and the crash window after the lock is released.

The status trigger is a second layer. Application code can have a bug. The database still refuses `queued` to `succeeded`. Checks tie results, errors, worker ids, and retry counts to the status so a partial update cannot commit a contradictory row.

Idempotency is deliberately narrower than the queue lock. The header protects a retried create. It does not make execution exactly-once. The retrospective accepts at-least-once execution because the jobs are pure functions.

## Security

The lab states its trust boundary instead of pretending a missing login page is a control. Ports bind to localhost. Containers run as a non-root user. Inputs are size-capped and schema-checked. ORM writes are parameterized. Logs and `job_events` omit payloads. HTTP 500 hides exception text because validation errors can contain the user's numbers or text. The STRIDE write-up in `docs/threat-model.md` lists the residual risks, including chunked bodies and the absence of authentication.

## Interface and accessibility

The page uses a skip link, labeled controls, and guidance tied to the job type with `aria-describedby`. Status badges include the words Queued, Running, Succeeded, Failed, Retrying, and Cancelled. Color repeats that text. It does not replace it. The recent-jobs region has a caption. Loading, empty, and error states are separate. The detail view announces failures with `role="alert"`. Focus outlines stay visible. Layout collapses below 800 pixels, and reduced-motion preferences shorten animation. Client-side checks catch an obvious Fibonacci bound before the request, and the server remains the authority.

## Biggest technical challenge

The hard part was the gap between "the worker locked the row" and "the worker finished the job." Holding the lock during the algorithm would serialize the whole database for the duration of the work. Releasing it creates orphans and stale writers. The lease, the version, and the worker id are three small fields that close that gap, and each one is easy to get slightly wrong. Tests had to cover the stale writer explicitly: recover the lease, then let the original worker try to save, and assert that the result does not change.

A related trap was JSON null versus SQL NULL. An unset result stored as JSON null failed the check that a non-succeeded job must have a SQL NULL result. The mapping uses `none_as_null` so absence and a JSON null inside a real result stay different.

## What would change for production

- Authenticate every request and scope list, get, and cancel to the owner.
- Put the database on a private network and stop publishing port 5432.
- Replace the static lease with a heartbeat that extends it, and alert when recovery fires often.
- Store large results outside the row and paginate the job list with a cursor.
- Run at least two workers and a migration job that is separate from request startup once more than one API replica exists. The advisory lock is correct for a couple of processes. A dedicated migration step is clearer in a fleet.
- Add rate limits per token. Input caps stop one huge job. They do not stop a tight loop of maximum-size jobs.
- Treat the generic failure sentence as a client message only, and keep a private operator diagnostic that is still scrubbed of payloads.
