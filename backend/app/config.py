"""Application configuration loaded from environment / .env.

Uses pydantic-settings so that every value is type-validated at startup —
fail fast on misconfiguration instead of discovering it mid-request.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The default JWT secret baked into the repo.  The startup validator
# refuses to run in production with this value still set.
_DEFAULT_DEV_JWT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    """Process-wide settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "algobattle"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database ---
    database_url: str = "postgresql+asyncpg://algobattle:algobattle@localhost:5432/algobattle"
    test_database_url: str = "sqlite+aiosqlite:///:memory:"
    sync_database_url: str = "postgresql+psycopg2://algobattle:algobattle@localhost:5432/algobattle"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    test_redis_url: str = "redis://localhost:6379/1"

    # --- JWT ---
    jwt_secret: str = _DEFAULT_DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    bcrypt_rounds: int = 12

    # --- Judge0 ---
    judge0_url: str = "http://localhost:2358"
    judge0_auth_token: str = ""
    judge0_poll_interval_seconds: float = 1.0
    judge0_timeout_seconds: int = 15
    # When Judge0 is unreachable, fall back to the unsandboxed local
    # subprocess runner.  The validator below defaults this to True in
    # development/test and False in production, so the safe value is
    # the default for any real deployment.
    judge_allow_local_fallback: bool | None = None

    # --- RQ ---
    rq_queue_name: str = "algobattle-judge"
    rq_worker_count: int = 2

    # Derived helpers --------------------------------------------------
    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def effective_database_url(self) -> str:
        return self.test_database_url if self.is_test else self.database_url

    @property
    def effective_redis_url(self) -> str:
        return self.test_redis_url if self.is_test else self.redis_url

    @property
    def judge0_auth_header(self) -> dict[str, str] | None:
        if not self.judge0_auth_token:
            return None
        return {"X-Auth-Token": self.judge0_auth_token}

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        """Fail fast on production-misconfiguration that would be silent bugs.

        - Default JWT secret: anyone with read access to the repo can forge
          tokens.  Refuse to start.
        - Local-judge fallback: runs user code in an unsandboxed subprocess
          on the host.  Defaults to off in production; dev/test defaults on.
        """
        if self.app_env == "production":
            if self.jwt_secret == _DEFAULT_DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET must be changed from the default value "
                    "before running in production. Set the JWT_SECRET env "
                    "var to a long random string."
                )
            # Force-disable the unsafe local-judge fallback in production
            # even if the operator set it via env (defence in depth).
            self.judge_allow_local_fallback = False
        else:
            # Default the fallback to True in dev/test if unset, so existing
            # local development workflows keep working.
            if self.judge_allow_local_fallback is None:
                self.judge_allow_local_fallback = True
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
