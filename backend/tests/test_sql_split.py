"""SQL script splitting used by the migration runner."""

from pathlib import Path

from northstar.migrate import split_sql


def test_dollar_quoted_function_stays_intact() -> None:
    script = """
    CREATE TABLE example (id INT);
    CREATE FUNCTION demo() RETURNS void
    LANGUAGE plpgsql
    AS $$
    BEGIN
        PERFORM 1;
    END;
    $$;
    """
    parts = split_sql(script)
    assert len(parts) == 2
    assert "PERFORM 1;" in parts[1]


def test_initial_migration_keeps_the_trigger_function_together() -> None:
    script = Path("database/migrations/001_initial.sql").read_text(encoding="utf-8")
    parts = split_sql(script)
    functions = [
        part for part in parts if "CREATE OR REPLACE FUNCTION enforce_job_status_transition" in part
    ]
    assert len(functions) == 1
    assert "RETURN NEW" in functions[0]
    assert all(";" not in part.split("$$")[0] or "FUNCTION" in part for part in functions)
