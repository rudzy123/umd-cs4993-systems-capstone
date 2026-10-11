"""In-process smoke test: submit each job type and observe completion."""

import pytest

from northstar_worker.loop import process_once

pytestmark = pytest.mark.usefixtures("clean_tables")


def test_submit_and_complete_each_supported_job(client, session_factory, settings) -> None:
    submissions = [
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
    job_ids: list[str] = []
    for job_type, payload, _check in submissions:
        response = client.post("/jobs", json={"job_type": job_type, "input": payload})
        assert response.status_code == 201, response.text
        job_ids.append(response.json()["id"])

    for _ in range(len(job_ids) + 2):
        if not process_once(session_factory, settings, "smoke-worker"):
            break

    for job_id, (_job_type, _payload, check) in zip(job_ids, submissions, strict=True):
        body = client.get(f"/jobs/{job_id}").json()
        assert body["status"] == "succeeded", body
        assert check(body)

    invalid = client.post("/jobs", json={"job_type": "fibonacci", "input": {"n": -1}})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert "Traceback" not in invalid.text
