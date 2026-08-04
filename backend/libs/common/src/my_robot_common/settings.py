from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "my-robot"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://myrobot:myrobot@localhost:5432/myrobot"
    redis_url: str = "redis://localhost:6379/0"

    emqx_host: str = "localhost"
    emqx_port: int = 1883
    emqx_ws_port: int = 8083
    emqx_username: str = "myrobot"
    emqx_password: str = "myrobot"

    jwt_secret: str = "dev-secret-change-me-please-32bytes-minimum"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    model_gateway_url: str = "http://localhost:8300"
    rag_engine_url: str = "http://localhost:8400"
    task_executor_url: str = "http://localhost:8500"
    user_tenant_url: str = "http://localhost:8200"


@lru_cache
def get_settings() -> Settings:
    return Settings()
