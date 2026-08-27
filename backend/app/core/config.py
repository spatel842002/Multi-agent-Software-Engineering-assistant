"""Application configuration, loaded and validated from environment variables.

Fails fast at startup with an actionable message if required settings are
missing or malformed, rather than surfacing a confusing error deep inside a
request handler later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # --- Auth ---
    jwt_secret_key: SecretStr = Field(
        ...,
        description="HMAC signing secret for JWT tokens. Generate with `openssl rand -hex 32`.",
    )
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    # --- Database ---
    database_url: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    # --- Redis (cache, rate limiting, Celery broker/result backend) ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Celery ---
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # --- Qdrant (dense retrieval) ---
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "code_chunks"

    # --- LLM provider (Ollama by default; free, local, no account required) ---
    llm_provider: Literal["ollama", "fake"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5-coder:1.5b"
    ollama_embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    # --- Object storage (S3-compatible; MinIO locally, AWS S3 in production) ---
    s3_endpoint_url: str | None = Field(
        default="http://localhost:9000", description="Set to None/unset to use real AWS S3."
    )
    s3_access_key: str = "minioadmin"
    s3_secret_key: SecretStr = SecretStr("minioadmin")
    s3_bucket_repositories: str = "masea-repositories"
    s3_region: str = "us-east-1"

    # --- MLflow ---
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment_name: str = "masea-evals"

    # --- Observability ---
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "masea-backend"
    enable_prometheus: bool = True

    # --- Rate limiting ---
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "10/minute"

    # --- Ingestion / sandbox safety ---
    ingestion_max_repo_size_mb: int = 500
    ingestion_clone_timeout_seconds: int = 120
    ingestion_allowed_schemes: tuple[str, ...] = ("https",)
    patch_sandbox_timeout_seconds: int = 60
    workspace_root: str = "./.workspace"

    # --- CORS ---
    cors_allow_origins: tuple[str, ...] = ("http://localhost:5173",)

    @field_validator("database_url")
    @classmethod
    def _validate_async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            raise ValueError(
                "database_url must use an async driver, e.g. 'postgresql+asyncpg://...' "
                "(got a plain 'postgresql://' URL)."
            )
        return v

    @property
    def celery_broker_url_resolved(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def celery_result_backend_resolved(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
