"""Worker loop shutdown behavior without a database."""

import threading
from pathlib import Path

from northstar.config import Settings
from northstar_worker.loop import make_signal_handler, run_until_stopped


def test_signal_handler_requests_stop() -> None:
    stop = threading.Event()
    make_signal_handler(stop)(15, None)
    assert stop.is_set()


def test_stop_before_start_does_not_poll(tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()
    called = {"count": 0}

    def process(*_args: object) -> bool:
        called["count"] += 1
        return False

    settings = Settings(poll_interval_seconds=0.2, heartbeat_path=str(tmp_path / "hb"))
    run_until_stopped(
        stop,
        session_factory=process,  # type: ignore[arg-type]
        settings=settings,
        worker_id="worker-stop",
        heartbeat=tmp_path / "hb",
        process=process,  # type: ignore[arg-type]
    )
    assert called["count"] == 0


def test_shutdown_finishes_current_iteration_only(tmp_path: Path) -> None:
    stop = threading.Event()
    calls = {"count": 0}

    def process(*_args: object) -> bool:
        calls["count"] += 1
        stop.set()
        return True

    settings = Settings(poll_interval_seconds=0.2)
    heartbeat = tmp_path / "heartbeat"
    run_until_stopped(
        stop,
        session_factory=process,  # type: ignore[arg-type]
        settings=settings,
        worker_id="worker-graceful",
        heartbeat=heartbeat,
        process=process,  # type: ignore[arg-type]
    )
    assert calls["count"] == 1
    assert heartbeat.is_file()
    assert float(heartbeat.read_text(encoding="utf-8")) > 0
