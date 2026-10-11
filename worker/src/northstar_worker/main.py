"""Process entrypoint."""

import logging
import signal
import threading
import uuid
from pathlib import Path

from northstar.bootstrap import prepare_for_serve
from northstar.config import get_settings
from northstar.db import make_engine, make_session_factory
from northstar.logging_config import configure_logging, log_event
from northstar_worker.loop import make_signal_handler, run_until_stopped, write_heartbeat

logger = logging.getLogger("northstar.worker")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()
    handler = make_signal_handler(stop)
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    heartbeat = Path(settings.heartbeat_path)
    worker_id = settings.worker_id or f"worker-{uuid.uuid4().hex[:12]}"
    engine = make_engine(settings.database_url)
    log_event(logger, "worker_starting", worker_id=worker_id)
    try:
        try:
            prepare_for_serve(
                engine,
                settings,
                stop,
                on_wait=lambda: write_heartbeat(heartbeat),
            )
        except RuntimeError:
            logger.error("database_not_ready")
            raise SystemExit(1) from None
        if stop.is_set():
            return
        log_event(logger, "worker_started", worker_id=worker_id)
        run_until_stopped(
            stop,
            make_session_factory(engine),
            settings,
            worker_id,
            heartbeat,
        )
    finally:
        engine.dispose()
        log_event(logger, "worker_stopped", worker_id=worker_id)


if __name__ == "__main__":
    main()
