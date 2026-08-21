from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_NAME: str = "ai-service"
    APP_DEBUG: bool = True

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]

    DATABASE_URL: str = "sqlite:///./app.db"

    # --- Companion (health companionship chat, streaming) ---
    COMPANION_MAX_HISTORY: int = 12

    # --- iFlytek Super Smart TTS (超拟人语音合成) ---
    # The frontend connects directly to iFlytek via an HMAC-SHA256 signed
    # WebSocket URL; we only need app_id / api_key / api_secret to sign.
    IFLYTEK_SMART_TTS_URL: str = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
    IFLYTEK_SMART_TTS_APP_ID: str = ""
    IFLYTEK_SMART_TTS_API_KEY: str = ""
    IFLYTEK_SMART_TTS_API_SECRET: str = ""

    # --- LLM backend (OpenAI-compatible: Ollama / vLLM / Aliyun DashScope / ...) ---
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: float = 0.0

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen3:14b"
    OLLAMA_TIMEOUT: float = 120.0

    # --- RBAC / knowledge-base scopes ---
    # HMAC secret used to sign elevated role tokens. When empty, elevated
    # roles (nurse/doctor/admin) cannot be registered; only the default
    # patient role is accepted. Set it to allow issuing doctor/admin tokens.
    RBAC_SIGNING_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
