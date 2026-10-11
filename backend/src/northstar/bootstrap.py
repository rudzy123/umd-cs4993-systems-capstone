"""Startup helpers shared by the API, worker, and migration command."""

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy import Engine

from northstar.config import Settings
from northstar.db import database_ready
from northstar.migrate import prepare_database

logger = logging.getLogger("northstar.bootstrap")


def wait_for_database(
    engine: Engine,
    stop: threading.Event,
    timeout_seconds: float,
    on_wait: Callable[[], None] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while not stop.is_set():
        if on_wait is not None:
            on_wait()
        if database_ready(engine):
            return True
        logger.warning("database_not_ready")
        if time.monotonic() >= deadline:
            return False
        if stop.wait(1):
            return False
    return False


def prepare_for_serve(
    engine: Engine,
    settings: Settings,
    stop: threading.Event,
    on_wait: Callable[[], None] | None = None,
) -> None:
    ready = wait_for_database(engine, stop, settings.database_wait_seconds, on_wait=on_wait)
    if stop.is_set():
        return
    if not ready:
        logger.error("database_not_ready")
        raise RuntimeError("database is not ready")
    prepare_database(engine, settings)
