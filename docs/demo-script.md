# Demo script

Five minutes. The stack is already up with `make up`. The UI is <http://127.0.0.1:8080>. The API is <http://127.0.0.1:8000>.

## 0:00 Opening

Say what the system does: a browser or HTTP client submits a bounded job, PostgreSQL stores it, a separate worker claims it with a row lock, and the page shows the result.

```bash
curl -s http://127.0.0.1:8000/ready
curl -s http://127.0.0.1:8080/healthz
```

Expected: the ready body includes `"status": "ready"`. The web check prints `ok`.

## 1:00 Happy path in the browser

On the home page, leave the job type on **Sort numbers**. The guidance mentions merge sort and the 10,000-number limit. Submit the prefilled `3, 1, 2`.

Expected: the recent-jobs table gains a row. The badge text moves from Queued to Running to Succeeded. Open the job. The result lists `1, 2, 3` and a comparison count. The badge includes the word Succeeded, not a color by itself.

## 2:00 The other three jobs

```bash
curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"shortest_path","input":{"nodes":["A","B","C"],"edges":[{"source":"A","target":"B","weight":1},{"source":"B","target":"C","weight":2},{"source":"A","target":"C","weight":10}],"source":"A","target":"C"}}'

curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"word_frequency","input":{"text":"The cat sat on the mat.","top_n":5}}'

curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"fibonacci","input":{"n":20}}'
```

Poll each `id` with `curl -s http://127.0.0.1:8000/jobs/<id>` or refresh the table. The table polls every 3 seconds. The detail page polls every 2 seconds.

Expected results:

- Shortest path: `path` is `A`, `B`, `C` and `distance` is 3.
- Word frequency: the first row is word `the` with count 2.
- Fibonacci: `value` is `6765`.

## 3:30 Failure path

Validation, which never creates a job:

```bash
curl -s -i -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"fibonacci","input":{"n":-1}}'
```

Expected: HTTP 422, `"code": "validation_error"`, a `details` entry for `n`, and no traceback.

In the browser, choose Fibonacci, replace `n` with `10001`, and submit. Expected: an alert that says to enter a whole number from 0 through 10000, and no new row.

Cancellation:

```bash
docker compose stop worker
curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"sort","input":{"numbers":[4,1]}}'
```

Copy the `id`, then:

```bash
curl -s -X POST http://127.0.0.1:8000/jobs/<id>/cancel
```

Expected: status `cancelled` and error summary `Cancelled by user.` A second cancel returns HTTP 409. Start the worker again with `docker compose start worker` before the next demo.

Retry behavior is easier to show with the test than with a crash:

```bash
pytest worker/tests/test_execution.py::test_retries_exhausted -q
```

Expected: the test passes. The job ends `failed` with the generic sentence, and the internal error text is absent from `error_summary`.

## 4:30 Close

Show one `job_events` trail if time remains:

```bash
docker compose exec postgres psql -U northstar -d northstar -c \
  "SELECT from_status, to_status, reason FROM job_events ORDER BY id DESC LIMIT 8;"
```

Shut down with `make down` when the demo is over.

## One-command check

```bash
python3 scripts/smoke_test.py
```

Expected lines: API ready, web ready, four `<type> <uuid> succeeded` lines, `validation error returned without a stack trace`, and `smoke test passed`.
