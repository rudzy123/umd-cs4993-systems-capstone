"""Audit logging does not echo submitted text."""

import logging

import pytest

pytestmark = pytest.mark.usefixtures("clean_tables")


def test_logs_omit_submitted_text(client, caplog) -> None:
    phrase = "super-secret-phrase"
    with caplog.at_level(logging.INFO, logger="northstar"):
        response = client.post(
            "/jobs",
            json={"job_type": "word_frequency", "input": {"text": phrase, "top_n": 5}},
        )
    assert response.status_code == 201
    for record in caplog.records:
        rendered = record.getMessage()
        extras = " ".join(
            str(value) for key, value in record.__dict__.items() if str(key).startswith("ns_")
        )
        assert phrase not in rendered
        assert phrase not in extras
