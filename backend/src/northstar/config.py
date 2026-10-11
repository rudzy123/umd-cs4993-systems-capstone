"""Runtime configuration loaded from the environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process settings.

    Environment variables use the ``NORTHSTAR_`` prefix, for example
    ``NORTHSTAR_DATABASE_URL``. Defaults are for a local Docker database and
    are not production credentials.
    """

    model_config = SettingsConfigDict(env_prefix="NORTHSTAR_", extra="ignore")

    database_url: str = "postgresql+psycopg://northstar:northstar@localhost:5432/northstar"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_retries: int = Field(default=2, ge=0, le=5)
    lease_seconds: int = Field(default=120, ge=5, le=3600)
    poll_interval_seconds: float = Field(default=0.5, ge=0.1, le=5.0)
    log_level: str = "INFO"
    migrations_dir: str = ""
    worker_id: str = ""
    heartbeat_path: str = "/tmp/northstar-worker-heartbeat"
    max_body_bytes: int = Field(default=1_048_576, ge=1024, le=5_000_000)
    database_wait_seconds: float = Field(default=60, ge=1, le=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()
