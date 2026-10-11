"""Apply versioned SQL files."""

import logging
import sys
import threading
from pathlib import Path

from sqlalchemy import Engine, text

from northstar.config import Settings, get_settings
from northstar.db import make_engine
from northstar.logging_config import configure_logging, log_event

logger = logging.getLogger("northstar.migrate")
ADVISORY_LOCK_KEY = 4993


def resolve_migrations_dir(settings: Settings) -> Path:
    candidates: list[Path] = []
    if settings.migrations_dir:
        candidates.append(Path(settings.migrations_dir))
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "database" / "migrations")
    candidates.append(Path.cwd() / "database" / "migrations")
    candidates.append(Path("/app/database/migrations"))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("database migrations directory was not found")


def apply_migrations(engine: Engine, directory: Path) -> list[str]:
    files = sorted(path for path in directory.glob("*.sql") if path.is_file())
    applied_now: list[str] = []
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
        connection.commit()
        try:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            connection.commit()
            rows = connection.execute(text("SELECT version FROM schema_migrations"))
            applied = {str(row[0]) for row in rows}
            for path in files:
                if path.name in applied:
                    continue
                statements = [
                    part for part in split_sql(path.read_text(encoding="utf-8")) if part.strip()
                ]
                for statement in statements:
                    connection.execute(text(statement))
                connection.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": path.name},
                )
                connection.commit()
                applied_now.append(path.name)
                log_event(logger, "migration_applied", version=path.name)
        except Exception:
            connection.rollback()
            raise
        finally:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": ADVISORY_LOCK_KEY},
                )
                connection.commit()
            except Exception:
                connection.rollback()
    if not applied_now:
        log_event(logger, "migrations_current")
    return applied_now


def prepare_database(engine: Engine, settings: Settings) -> list[str]:
    return apply_migrations(engine, resolve_migrations_dir(settings))


def split_sql(script: str) -> list[str]:
    """Split a SQL script on semicolons that are outside quotes and comments."""

    statements: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(script)
    dollar_tag: str | None = None
    in_single = False
    in_line_comment = False
    in_block_comment = False
    while index < length:
        char = script[index]
        nxt = script[index + 1] if index + 1 < length else ""
        if in_line_comment:
            buffer.append(char)
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            buffer.append(char)
            if char == "*" and nxt == "/":
                buffer.append(nxt)
                index += 2
                in_block_comment = False
                continue
            index += 1
            continue
        if dollar_tag is not None:
            if script.startswith(dollar_tag, index):
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            buffer.append(char)
            index += 1
            continue
        if in_single:
            buffer.append(char)
            if char == "'" and nxt == "'":
                buffer.append(nxt)
                index += 2
                continue
            if char == "'":
                in_single = False
            index += 1
            continue
        if char == "-" and nxt == "-":
            in_line_comment = True
            buffer.append(char)
            index += 1
            continue
        if char == "/" and nxt == "*":
            in_block_comment = True
            buffer.append(char)
            index += 1
            continue
        if char == "'":
            in_single = True
            buffer.append(char)
            index += 1
            continue
        if char == "$":
            tag = _dollar_tag(script, index)
            if tag is not None:
                dollar_tag = tag
                buffer.append(tag)
                index += len(tag)
                continue
        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue
        buffer.append(char)
        index += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def _dollar_tag(script: str, index: int) -> str | None:
    if script[index] != "$":
        return None
    cursor = index + 1
    while cursor < len(script) and (script[cursor].isalnum() or script[cursor] == "_"):
        cursor += 1
    if cursor < len(script) and script[cursor] == "$":
        return script[index : cursor + 1]
    return None


def main() -> None:
    from northstar.bootstrap import wait_for_database

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    stop = threading.Event()
    try:
        if not wait_for_database(engine, stop, settings.database_wait_seconds):
            logger.error("database_not_ready")
            raise SystemExit(1)
        prepare_database(engine, settings)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from None
