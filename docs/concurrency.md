# Concurrency

Two workers must not execute one job at the same time. The result would be wasted work at best and a lost update at worst: both would read `queued`, both would compute, and the later write would overwrite the earlier result or trip the status trigger. Northstar prevents that with a database lock, a version, and a worker id. It does not depend on a process holding a mutex across machines.

## Claim

`claim_next_job` opens a transaction and runs:

```sql
SELECT ...
FROM jobs
WHERE status IN ('queued', 'retrying')
ORDER BY created_at, id
LIMIT 1
FOR UPDATE SKIP LOCKED
```

`SKIP LOCKED` makes a second worker skip a row the first worker has locked and take the next row, or find nothing. The claim then sets `running`, stores `worker_id`, increments `version`, sets `lease_expires_at`, and inserts an attempt and a `claimed` event. The transaction commits before any algorithm runs. Holding the row lock during a 10,000-step Fibonacci computation would block recovery and cancellation checks for no benefit.

The partial index `jobs_claim_idx` covers `(created_at, id)` where status is `queued` or `retrying`.

## Transaction boundaries

| Step | Transaction |
| --- | --- |
| Create, idempotency check, `accepted` event | One transaction in `create_job` |
| Claim, attempt insert, `claimed` event | One transaction, committed before CPU work |
| Success or failure write | A new transaction that updates the job only if version and worker id still match |
| Lease recovery | One transaction that locks expired `running` rows with `SKIP LOCKED` |
| Cancel | `SELECT … FOR UPDATE` and a status change only from `queued` or `retrying` |
| Migrations | One transaction per file, while session advisory lock `4993` is held |

A crash after commit and before execution leaves a `running` row with a future lease. That is intentional. The job is owned until the lease expires.

## Crash scenarios

| Crash | Outcome |
| --- | --- |
| API dies before commit | The job is absent. The client can retry. Without an idempotency key, a retry that did commit and whose response was lost creates a second job. |
| Worker dies after claim, before completion | The row stays `running` until `lease_expires_at`. Another worker's recovery pass requeues it if `retry_count < max_retries`, or marks it `failed` if the budget is spent. Open attempts are closed with a lease message. |
| Worker dies during the completion transaction | PostgreSQL rolls the transaction back. The job stays `running` and is recovered by the lease. |
| Two workers claim together | One locks the row. The other skips it. Tests start two threads at a barrier ten times and require exactly one claim and one attempt. |
| Worker finishes after its lease was recovered | The completion update matches on version and worker id, finds no row, writes `ownership_lost`, and does not change the result. |

## Retries

`retry_count` starts at 0. `max_retries` is copied onto the job at creation from `NORTHSTAR_MAX_RETRIES` (default 2, range 0–5).

- An unexpected exception is retryable. If retries remain, `retry_count` increments and the status becomes `retrying`. Otherwise the status becomes `failed` and the client sees `The job could not be completed. Please submit it again.`
- `JobExecutionError` and a stored payload that fails validation are permanent. They do not consume the retry budget as a requeue. The user-facing text does not include the bad value.
- Lease expiry follows the same budget. The messages are `The previous attempt stopped before it finished. The job will be retried.` or `The job stopped before it finished and has no retries remaining.`

The poll interval defaults to 0.5 seconds and is bounded to the range 0.1–5. Shutdown sets an event on SIGTERM or SIGINT. The current iteration finishes, and an idle wait uses `Event.wait` so it can return early.

## Idempotency limitations

`Idempotency-Key` plus a fingerprint makes a replay return the original job with HTTP 200. The same key with a different canonical body returns 409.

Without the header, `POST /jobs` is not idempotent. A lost response followed by a client retry creates two jobs. Completion is not exactly-once in the real world: a worker can run the algorithm and crash before the success commit, and recovery will run it again. The algorithms only return a value. They do not send mail, charge a card, or write to a second system. That is why at-least-once execution is acceptable here.

## Orphaned running jobs

A job is orphaned when its status is `running` and `lease_expires_at` is in the past. `recover_expired_leases` runs at the start of every worker iteration. It locks those rows with `SKIP LOCKED`, so two recovery passes do not reclaim the same row. The lease default is 120 seconds. Tests use 30 seconds. A fresh lease is left alone.

Recovery increments `version` and clears `worker_id`. The original worker's later update cannot match.

## What the database still enforces

The trigger `enforce_job_status_transition` rejects updates that skip states, including `queued` directly to `succeeded`. Check constraints require a result only when the status is `succeeded`, an error summary when the status is `failed`, a worker id while `running`, and `retry_count <= max_retries`. Application bugs that forget a field fail the commit instead of storing a contradictory row.
