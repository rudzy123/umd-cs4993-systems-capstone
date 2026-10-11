# Testing strategy

Tests run without the public internet. They need a local PostgreSQL for anything that touches the schema. Algorithm tests, validation tests, the SQL splitter test, and the worker shutdown test do not.

## Backend

| Area | Location | What it proves |
| --- | --- | --- |
| Algorithms | `backend/tests/test_algorithms.py` | Contracts, determinism, limits, and the documented examples |
| Validation | `backend/tests/test_validation.py` | Rejected types, extra fields, bounds |
| API | `backend/tests/test_api.py` | Create, get, list, errors, idempotency, cancel, body size, CORS, hidden 500 text |
| Security log | `backend/tests/test_security.py` | Submitted text is not written to the log stream |
| SQL splitter | `backend/tests/test_sql_split.py` | Dollar quotes stay intact |

The API suite uses a session-scoped `TestClient` with `raise_server_exceptions=False`, so the generic 500 handler is what the test observes. Each test truncates `job_events`, `job_attempts`, and `jobs`. `schema_migrations` is left in place.

## Worker

| Area | Location | What it proves |
| --- | --- | --- |
| Claim | `worker/tests/test_claim.py` | A second claim sees nothing. Two threads across 10 barriers produce one claim and one attempt |
| Execution | `worker/tests/test_execution.py` | Success, corrupt payload, retry then success, exhausted retries, stale worker fence |
| Recovery | `worker/tests/test_recovery.py` | Expired lease requeues or fails. A fresh lease is kept |
| Shutdown | `worker/tests/test_shutdown.py` | The signal handler sets the event. A stopped loop does not poll. One in-flight iteration finishes and the heartbeat is written |

## Database

`tests/test_migrations.py` drops and recreates `northstar_migration_test`, applies migrations twice, checks `jobs_status_updated_idx`, rejects `queued` to `succeeded`, and rejects `succeeded` without a result. Each failing statement uses its own transaction so a caught error does not abort a later statement.

## Frontend

Vitest and React Testing Library, with `cleanup` after each test.

| Area | Location |
| --- | --- |
| Form parsing | `frontend/src/forms.test.ts` |
| Status text | `frontend/src/components/StatusBadge.test.tsx` |
| Form labels and client-side rejection | `frontend/src/components/JobForm.test.tsx` |
| Loading, empty, error, and table states | `frontend/src/components/JobTable.test.tsx` |
| Result rendering | `frontend/src/components/ResultView.test.tsx` |
| API client | `frontend/src/api.test.ts` uses a mocked `fetch` against `http://api.test` |
| Page accessibility | `frontend/src/pages/HomePage.test.tsx` checks the heading, the sort guidance, and the empty state |

ESLint includes the `jsx-a11y` rules. Status is text in the badge, not color alone. The production build runs `tsc --noEmit` and Vite.

## System

`tests/e2e/test_smoke.py` submits all four job types through the API test client, drives `process_once` until each job finishes, checks the results, and checks that Fibonacci `n = -1` returns 422.

`scripts/smoke_test.py` is the live check. It uses only the Python standard library. It waits for the API `/ready` and the web `/healthz`, submits the same four jobs to a running worker, and checks the validation failure. CI runs it after `docker compose up --build -d --wait`.

## CI

`.github/workflows/ci.yml` has four jobs:

1. Backend: Python 3.12, PostgreSQL 16, Ruff, mypy, pytest.
2. Frontend: Node 22, `npm ci`, lint, test, production build.
3. Docker image builds for the API, worker, and frontend.
4. Compose stack plus `scripts/smoke_test.py`.

Workflow permissions are `contents: read`.

## Gaps

The concurrent claim test uses threads in one process and two sessions. That matches PostgreSQL row locking. It does not start two operating-system processes. The live smoke test covers the real worker process when Compose is available.

Browser automation is not part of CI. Component tests render the pages in jsdom.
