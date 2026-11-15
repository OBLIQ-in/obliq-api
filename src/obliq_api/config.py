from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "obliq-api"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = Field(..., min_length=32)

    # API
    api_v1_prefix: str = "/v1"
    max_upload_size_mb: int = 50
    max_pages_per_job: int = 200
    sync_page_threshold: int = 5
    job_result_ttl_seconds: int = 3600
    processing_timeout_seconds: int = 1800

    # Database (sized for serverless replica scaling against Neon limits)
    database_url: PostgresDsn
    database_pool_size: int = 3
    database_max_overflow: int = 2

    # Redis
    redis_url: RedisDsn
    redis_job_prefix: str = "obliq:job:"
    redis_rate_prefix: str = "obliq:rate:"

    # Credits
    starting_credits: int = 10_000
    credits_per_page: int = 1

    # Auth
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    api_key_prefix: str = "obliq_live_"
    internal_key_prefix: str = "obliq_internal_"
    bcrypt_rounds: int = 12

    # Rate limits
    rate_limit_requests_per_minute: int = 60
    rate_limit_pages_per_minute: int = 120

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "obliq-api"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
