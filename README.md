# Northstar Job Lab

Northstar Job Lab is a small, locally deployable distributed job system for the UMD CS 4993 systems capstone. A person submits a bounded computational job through a web page or a REST API. The API validates the input, stores the job in PostgreSQL, and returns an identifier. A separate worker process claims the job, runs one of four algorithms, stores the result, and updates the job state. The page polls until the result or a user-safe failure appears.

## Problem statement

Many courses teach algorithms, operating systems, networking, databases, security, and interface design as separate units. This lab puts those units in one running system. The interesting part is not any single algorithm. It is the contract around the algorithm: a validated request, a durable queue, a worker that can crash, a database transaction that prevents two workers from executing the same job, and an interface that reports status without relying on color alone.

The system stays on one machine. It does not use Redis, a cloud queue, or an external identity provider.

## Learning objectives

- Define a strict input contract and a deterministic output for each algorithm.
- Move a job across process boundaries with HTTP and a shared database.
- Claim work with `SELECT … FOR UPDATE SKIP LOCKED` so concurrent workers do not double-execute a job.
- Recover a job whose worker disappeared by using a lease instead of assuming the process is still alive.
- Keep failure messages useful to a person while withholding stack traces, SQL, and raw exception text.
- Build a keyboard-accessible interface with loading, empty, error, and success states.

## Architecture summary

The repository is a monorepo with four runtime pieces:

| Piece | Role |
| --- | --- |
| `frontend/` | React, TypeScript, and Vite. In Docker, nginx serves the built page and proxies `/api/` to the API. |
| `backend/` | FastAPI application and the shared `northstar` library: models, algorithms, validation, and queue services. |
| `worker/` | Separate Python process. It polls, claims, executes, and recovers expired leases. |
| `database/migrations/` | Ordered SQL migrations. The API and the worker apply them on startup under a PostgreSQL advisory lock. |

The worker imports the shared library. It does not call the HTTP API to claim work. The database is the queue.

```mermaid
flowchart LR
    person[Person]
    browser[Web browser]
    api[Northstar API]
    worker[Northstar worker]
    db[(PostgreSQL)]

    person --> browser
    person --> api
    browser --> api
    api --> db
    worker --> db
```

```mermaid
flowchart TB
    subgraph host [Local machine]
        subgraph web [frontend container]
            nginx[nginx static files and /api proxy]
        end
        subgraph app [api container]
            fastapi[FastAPI and uvicorn]
        end
        subgraph exec [worker container]
            loop[Polling worker process]
        end
        subgraph data [postgres container]
            pg[(PostgreSQL 16)]
        end
    end

    nginx -->|HTTP /api| fastapi
    fastapi -->|SQLAlchemy and psycopg| pg
    loop -->|claim, execute, recover| pg
```

## Job types

| Type | Work | Bound |
| --- | --- | --- |
| `sort` | Stable merge sort of a numeric list | 10,000 numbers, magnitude at most 1e15 |
| `shortest_path` | Dijkstra on a weighted graph with non-negative weights | 300 nodes, 2,000 edges |
| `word_frequency` | Token counts, ranked by count then word | 100,000 characters, `top_n` from 1 to 100 |
| `fibonacci` | Bottom-up dynamic programming | `n` from 0 through 10,000 |

States are `queued`, `running`, `succeeded`, `failed`, `retrying`, and `cancelled`. A queued or retrying job can be cancelled. A running job cannot, because the worker may already be inside the algorithm.

## Local setup

Requirements for the Docker path: Docker Compose, and Python 3.12 if you want to run the smoke script on the host. The frontend image builds itself.

```bash
cp .env.example .env
make up
```

Compose binds PostgreSQL to `127.0.0.1:5432`, the API to `127.0.0.1:8000`, and the web UI to `127.0.0.1:8080`. The API and worker wait for PostgreSQL, then apply `database/migrations/` before serving or polling. The default database password `northstar` is a local-lab value. Override it with `NORTHSTAR_DB_PASSWORD` before `make up`. Do not publish these ports beyond localhost.

Open <http://127.0.0.1:8080>.

Without Docker, install Python 3.12 dependencies and the frontend, start PostgreSQL yourself, then:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e "./backend[dev]" -e "./worker[dev]"
cd frontend && npm install && cd ..
export NORTHSTAR_DATABASE_URL=postgresql+psycopg://northstar:northstar@127.0.0.1:5432/northstar
python -m northstar.migrate
uvicorn northstar.api.app:create_app --factory --host 127.0.0.1 --port 8000
python -m northstar_worker
cd frontend && npm run dev
```

The Vite dev server listens on <http://127.0.0.1:5173> and proxies `/api` to the API. CORS in the default settings allows that origin.

## Test commands

```bash
make lint
make test
make test-frontend
make build-frontend
```

`make test` starts the Compose PostgreSQL service and runs pytest. Integration tests use `NORTHSTAR_TEST_DATABASE_URL`, which defaults to `postgresql+psycopg://northstar:northstar@127.0.0.1:5432/northstar_test`. The suite creates that database when the server is reachable.

Frontend checks, from `frontend/`:

```bash
npm run lint
npm test
npm run build
```

## Demo

With the stack up:

```bash
python3 scripts/smoke_test.py
```

The script waits for `/ready` and the web health check, submits one of each job type, checks the results, and confirms that Fibonacci `n = -1` returns HTTP 422 with `validation_error` and no stack trace. A five-minute walkthrough, including a failure path, is in [docs/demo-script.md](docs/demo-script.md).

## Shutdown

```bash
make down
```

`make down` stops containers and leaves the named volume in place. `docker compose down -v` also deletes the database volume.

## Limitations

- There is no authentication. The lab assumes a trusted localhost.
- Cancellation applies only to `queued` and `retrying` jobs.
- A running attempt is protected by a lease, default 120 seconds, not by a cooperative cancel.
- `POST /jobs` is not idempotent unless the client sends an `Idempotency-Key` header.
- The same idempotency key with a different body returns 409. Replaying the same key and body returns the original job.
- Chunked request bodies without `Content-Length` are not rejected by the size limit.
- Unexpected execution errors retry up to `max_retries` (default 2, at most 5). The client sees a generic sentence, not the exception text.
- Input that fails validation after it was stored, and explicit `JobExecutionError` failures, are permanent.
- Dijkstra accepts only non-negative weights. An unreachable target is a successful result with `reachable: false`.
- The worker executes jobs one at a time inside its process. Scale-out means more worker processes, not threads inside one job.

## Future improvements

- Add authentication and per-user job ownership before any non-local deployment.
- Stream progress for long Fibonacci or sort jobs instead of polling the whole document.
- Move large results to object storage and keep only a pointer in PostgreSQL.
- Add a dead-letter inspection page for operators.
- Replace the fixed lease with a heartbeat that extends the lease while a job is still making progress.

## Documentation map

- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Algorithms](docs/algorithms.md)
- [Concurrency](docs/concurrency.md)
- [Database design](docs/database-design.md)
- [Testing strategy](docs/testing-strategy.md)
- [Operations](docs/operations.md)
- [Demo script](docs/demo-script.md)
- [Learning retrospective](docs/learning-retrospective.md)

## License

MIT. See [LICENSE](LICENSE).
