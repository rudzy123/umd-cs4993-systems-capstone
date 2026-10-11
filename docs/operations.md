# Operations

## Start

```bash
cp .env.example .env
make up
```

`make up` is `docker compose up --build -d --wait`. Compose waits until health checks pass.

| Service | Check |
| --- | --- |
| postgres | `pg_isready -U northstar -d northstar` |
| api | HTTP GET `http://127.0.0.1:8000/ready` from inside the container |
| worker | Heartbeat file mtime is less than 30 seconds old |
| frontend | HTTP GET `/healthz` returns `ok` |

`depends_on` waits for the database health check before the API and worker start, and for the API health check before the frontend starts. Each application also waits in code, because a healthy database can still refuse connections for a moment.

The API and worker images run as uid 10001. The worker has `init: true` and `stop_grace_period: 20s`.

## Migrations

Startup applies pending files. To run them explicitly:

```bash
make migrate
```

That starts PostgreSQL if needed and runs `python -m northstar.migrate` in the API image. On a host virtualenv, with `NORTHSTAR_DATABASE_URL` set:

```bash
python -m northstar.migrate
```

Files run in lexical order. Applied names are stored in `schema_migrations`.

## Shutdown

The worker handles SIGTERM and SIGINT by setting a stop event. The current claim or completion finishes. The idle poll returns as soon as the event is set. Compose sends SIGTERM and waits 20 seconds.

```bash
make down
```

To remove the database volume as well:

```bash
docker compose down -v
```

## Logs

Application logs are one JSON object per line on stdout. Useful fields include `message`, `ns_job_id`, `ns_worker_id`, and `ns_exception_type`. Do not expect payloads in the log.

```bash
docker compose logs -f api worker
```

`job_events` is the audit trail for status changes.

## Configuration

| Variable | Default in code | Role |
| --- | --- | --- |
| `NORTHSTAR_DATABASE_URL` | local `northstar` database | SQLAlchemy URL |
| `NORTHSTAR_DB_PASSWORD` | `northstar` in Compose | Substituted into the Compose URL |
| `NORTHSTAR_CORS_ORIGINS` | localhost ports 5173 | Comma-separated browser origins |
| `NORTHSTAR_MAX_RETRIES` | 2 | Copied onto each new job. Range 0–5 |
| `NORTHSTAR_LEASE_SECONDS` | 120 | Running-job ownership window |
| `NORTHSTAR_POLL_INTERVAL_SECONDS` | 0.5 | Idle wait. Range 0.1–5 |
| `NORTHSTAR_MAX_BODY_BYTES` | 1048576 | Content-Length ceiling |
| `NORTHSTAR_WORKER_ID` | empty, then a random id | Stable id when you want one |
| `NORTHSTAR_MIGRATIONS_DIR` | discovered, or `/app/database/migrations` in images | SQL directory |
| `NORTHSTAR_LOG_LEVEL` | INFO | Python log level |
| `NORTHSTAR_HEARTBEAT_PATH` | `/tmp/northstar-worker-heartbeat` | Health file |
| `VITE_API_BASE_URL` | `/api` | Frontend base URL, baked in at build time |

Change `NORTHSTAR_DB_PASSWORD` before starting Compose on a shared machine. Do not commit `.env`.

## Backup and restore

The Compose volume is named `northstar-pg`. From the repository directory, while the database is running:

```bash
docker compose exec -T postgres pg_dump -U northstar -d northstar --format=custom > northstar.dump
```

Restore into an empty database:

```bash
docker compose exec -T postgres pg_restore -U northstar -d northstar --clean --if-exists < northstar.dump
```

A logical dump is enough for this lab. Stop the worker before restoring so it does not claim rows mid-restore. After a restore, start the API or run `python -m northstar.migrate` so any newer migration files still get applied.

Host-installed PostgreSQL uses the same `pg_dump` and `pg_restore` commands against `127.0.0.1`.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| API `/ready` returns 503 | Database is down, the URL is wrong, or the password does not match. The response does not include the URL. Read the API log for `exception_type`. |
| Jobs stay `queued` | The worker is not running, or it cannot connect. `docker compose ps` should show the worker healthy. A missing heartbeat means the loop is stuck or the process exited. |
| Jobs stay `running` | The worker died and the lease has not expired. Wait for `NORTHSTAR_LEASE_SECONDS`, or start a worker and let recovery run. |
| HTTP 409 on cancel | The job is `running`, `succeeded`, `failed`, or already `cancelled`. Only `queued` and `retrying` cancel. |
| HTTP 409 on create with an idempotency key | The key was already used with a different body. |
| HTTP 413 | The `Content-Length` exceeds `NORTHSTAR_MAX_BODY_BYTES`. |
| HTTP 422 | Read `error.details`. The input failed validation. |
| HTTP 500 with a generic message | An unexpected server error. The log has the exception type and not a traceback. |
| Browser shows a network error from Vite | The API is not on port 8000, or the origin is missing from `NORTHSTAR_CORS_ORIGINS`. |
| Migration fails on a second machine | Confirm both processes share `NORTHSTAR_MIGRATIONS_DIR` and the database. The advisory lock serializes the runners. |
| Compose port 5432 is in use | Stop the other PostgreSQL or change the host port in `docker-compose.yml`. |

## Health endpoints

`GET /health` means the process accepted the request. `GET /ready` means the database answered `SELECT 1`. Use `/ready` for orchestration. A load balancer that uses `/health` will send traffic before migrations finish.
