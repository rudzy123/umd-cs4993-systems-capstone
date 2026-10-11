#!/usr/bin/env python3
"""Submit one of each job type to a running Northstar stack and wait for results."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("NORTHSTAR_API_URL", "http://127.0.0.1:8000").rstrip("/")
WEB = os.environ.get("NORTHSTAR_WEB_URL", "http://127.0.0.1:8080").rstrip("/")


def request(
    method: str, url: str, payload: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            parsed: dict[str, object]
            try:
                loaded = json.loads(body) if body else {}
            except json.JSONDecodeError:
                loaded = {"raw": body}
            if not isinstance(loaded, dict):
                raise SystemExit(f"Expected a JSON object from {url}")
            parsed = loaded
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        if not isinstance(parsed, dict):
            parsed = {"raw": raw}
        return exc.code, parsed


def wait_for(url: str, label: str) -> None:
    deadline = time.monotonic() + 90
    last = "not started"
    while time.monotonic() < deadline:
        try:
            status, body = request("GET", url)
            if status == 200:
                print(f"{label} ready")
                return
            last = f"HTTP {status} {body}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1)
    raise SystemExit(f"{label} did not become ready: {last}")


def wait_for_job(job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, body = request("GET", f"{API}/jobs/{job_id}")
        if status != 200:
            raise SystemExit(f"Could not read job {job_id}: {status} {body}")
        state = body.get("status")
        if state in {"succeeded", "failed", "cancelled"}:
            return body
        time.sleep(0.5)
    raise SystemExit(f"Timed out waiting for job {job_id}")


def main() -> None:
    wait_for(f"{API}/ready", "API")
    wait_for(f"{WEB}/healthz", "Web")
    home_status, _home = request("GET", f"{WEB}/")
    if home_status != 200:
        raise SystemExit(f"Web UI returned HTTP {home_status}")

    jobs = [
        (
            "sort",
            {"numbers": [5, 1, 4, 2, 3]},
            lambda body: body["result"]["sorted"] == [1, 2, 3, 4, 5],
        ),
        (
            "shortest_path",
            {
                "nodes": ["A", "B", "C"],
                "edges": [
                    {"source": "A", "target": "B", "weight": 1},
                    {"source": "B", "target": "C", "weight": 2},
                    {"source": "A", "target": "C", "weight": 10},
                ],
                "source": "A",
                "target": "C",
            },
            lambda body: (
                body["result"]["path"] == ["A", "B", "C"] and body["result"]["distance"] == 3
            ),
        ),
        (
            "word_frequency",
            {"text": "The cat sat on the mat.", "top_n": 5},
            lambda body: body["result"]["frequencies"][0] == {"word": "the", "count": 2},
        ),
        ("fibonacci", {"n": 20}, lambda body: body["result"]["value"] == "6765"),
    ]
    for job_type, payload, check in jobs:
        status, created = request("POST", f"{API}/jobs", {"job_type": job_type, "input": payload})
        if status != 201:
            raise SystemExit(f"{job_type} submit failed: {status} {created}")
        job_id = str(created["id"])
        finished = wait_for_job(job_id)
        if finished.get("status") != "succeeded" or not check(finished):
            raise SystemExit(f"{job_type} finished unexpectedly: {finished}")
        print(f"{job_type} {job_id} succeeded")

    status, invalid = request("POST", f"{API}/jobs", {"job_type": "fibonacci", "input": {"n": -1}})
    error = invalid.get("error")
    if status != 422 or not isinstance(error, dict) or error.get("code") != "validation_error":
        raise SystemExit(f"Expected a validation error, got {status} {invalid}")
    print("validation error returned without a stack trace")
    print("smoke test passed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
