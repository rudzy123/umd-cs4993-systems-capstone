"""Polling loop for the Northstar worker."""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from northstar.config import Settings
from northstar.services.queue import claim_next_job, execute_claimed_job, recover_expired_leases

logger = logging.getLogger("northstar.worker")
ProcessOnce = Callable[[sessionmaker[Session], Settings, str], bool]


def process_once(
    session_factory: sessionmaker[Session], settings: Settings, worker_id: str
) -> bool:
    recover_expired_leases(session_factory)
    claimed = claim_next_job(session_factory, worker_id, settings)
    if claimed is None:
        return False
    execute_claimed_job(session_factory, claimed)
    return True


def run_until_stopped(
    stop: threading.Event,
    session_factory: sessionmaker[Session],
    settings: Settings,
    worker_id: str,
    heartbeat: Path | None = None,
    process: ProcessOnce = process_once,
) -> None:
    """Poll until ``stop`` is set.

    The current database claim finishes before the loop notices the stop
    event. Bounded ``Event.wait`` keeps an idle worker responsive to SIGTERM.
    """

    while not stop.is_set():
        write_heartbeat(heartbeat)
        try:
            worked = process(session_factory, settings, worker_id)
        except Exception as exc:
            logger.error(
                "worker_iteration_failed",
                extra={"ns_exception_type": type(exc).__name__, "ns_worker_id": worker_id},
            )
            worked = False
        write_heartbeat(heartbeat)
        if stop.is_set():
            break
        if not worked:
            stop.wait(settings.poll_interval_seconds)


def make_signal_handler(stop: threading.Event) -> Callable[[int, object], None]:
    def handle(_signum: int, _frame: object) -> None:
        stop.set()

    return handle


def write_heartbeat(heartbeat: Path | None) -> None:
    if heartbeat is None:
        return
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text(str(time.time()), encoding="utf-8")
