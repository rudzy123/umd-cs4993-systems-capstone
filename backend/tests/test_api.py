"""HTTP API tests."""

import uuid

import pytest

from northstar_worker.loop import process_once

pytestmark = pytest.mark.usefixtures("clean_tables")


def test_health_and_ready(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_create_get_and_list_jobs(client) -> None:
    created = client.post("/jobs", json={"job_type": "sort", "input": {"numbers": [3, 1, 2]}})
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "queued"
    assert body["input"] == {"numbers": [3, 1, 2]}
    fetched = client.get(f"/jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]
    listing = client.get("/jobs")
    assert listing.status_code == 200
    assert listing.json()["jobs"][0]["id"] == body["id"]


def test_validation_error_shape(client) -> None:
    response = client.post("/jobs", json={"job_type": "fibonacci", "input": {"n": 100000}})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["details"]
    assert "Traceback" not in response.text


def test_unknown_field_is_rejected(client) -> None:
    response = client.post(
        "/jobs",
        json={"job_type": "sort", "input": {"numbers": [1]}, "note": "nope"},
    )
    assert response.status_code == 422


def test_missing_job_and_bad_uuid(client) -> None:
    missing = client.get(f"/jobs/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    invalid = client.get("/jobs/not-a-uuid")
    assert invalid.status_code == 422
    assert "Traceback" not in invalid.text


def test_idempotency_replay_and_conflict(client) -> None:
    headers = {"Idempotency-Key": "demo-key-1"}
    first = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "fibonacci", "input": {"n": 6}},
    )
    second = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "fibonacci", "input": {"n": 6}},
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    conflict = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "fibonacci", "input": {"n": 7}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_cancel_queued_job_and_reject_second_cancel(client) -> None:
    created = client.post("/jobs", json={"job_type": "sort", "input": {"numbers": [1]}})
    job_id = created.json()["id"]
    cancelled = client.post(f"/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["error_summary"] == "Cancelled by user."
    again = client.post(f"/jobs/{job_id}/cancel")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"


def test_cancel_after_success_conflicts(client, session_factory, settings) -> None:
    created = client.post("/jobs", json={"job_type": "sort", "input": {"numbers": [2, 1]}})
    job_id = created.json()["id"]
    assert process_once(session_factory, settings, "api-worker") is True
    finished = client.get(f"/jobs/{job_id}")
    assert finished.json()["status"] == "succeeded"
    assert finished.json()["result"]["sorted"] == [1, 2]
    denied = client.post(f"/jobs/{job_id}/cancel")
    assert denied.status_code == 409


def test_list_limit_validation(client) -> None:
    client.post("/jobs", json={"job_type": "fibonacci", "input": {"n": 1}})
    client.post("/jobs", json={"job_type": "fibonacci", "input": {"n": 2}})
    limited = client.get("/jobs", params={"limit": 1})
    assert limited.status_code == 200
    assert len(limited.json()["jobs"]) == 1
    invalid = client.get("/jobs", params={"limit": 0})
    assert invalid.status_code == 422


def test_payload_too_large(client) -> None:
    response = client.post(
        "/jobs",
        content=b'{"job_type":"sort","input":{"numbers":[1]}}' + b" " * 3000,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert "Traceback" not in response.text


def test_cors_allows_the_local_ui_only(client) -> None:
    allowed = client.options(
        "/jobs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    rejected = client.get("/health", headers={"Origin": "https://evil.example"})
    assert rejected.headers.get("access-control-allow-origin") is None


def test_internal_errors_hide_exception_text(client, monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("secret-db-password")

    monkeypatch.setattr("northstar.api.routes.job_service.create_job", explode)
    response = client.post("/jobs", json={"job_type": "sort", "input": {"numbers": [1]}})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret-db-password" not in response.text
    assert "Traceback" not in response.text
