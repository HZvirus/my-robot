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

    # --- General chat (streaming, context-aware) ---
    CHAT_MAX_HISTORY: int = 10

    # --- Companion (health companionship chat, streaming) ---
    COMPANION_MAX_HISTORY: int = 12

    # --- iFlytek TTS (voice read-aloud, v2 online TTS) ---
    IFLYTEK_APP_ID: str = ""
    IFLYTEK_API_KEY: str = ""
    IFLYTEK_API_SECRET: str = ""
    IFLYTEK_TTS_URL: str = "wss://tts-api.xfyun.cn/v2/tts"
    IFLYTEK_TTS_VOICE: str = "xiaoyan"
    IFLYTEK_TTS_SPEED: int = 50
    IFLYTEK_TTS_VOLUME: int = 50
    IFLYTEK_TTS_PITCH: int = 50
    IFLYTEK_TTS_MAX_BYTES: int = 8000

    # --- iFlytek Super Smart TTS (超拟人语音合成, independent of v2) ---
    # AUTH_METHOD: 1 = x-api-key header with APIPassword, 2 = HMAC-SHA256 signed URL
    IFLYTEK_SMART_TTS_URL: str = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
    IFLYTEK_SMART_TTS_AUTH_METHOD: int = 1
    IFLYTEK_SMART_TTS_APP_ID: str = ""
    IFLYTEK_SMART_TTS_API_KEY: str = ""
    IFLYTEK_SMART_TTS_API_SECRET: str = ""
    IFLYTEK_SMART_TTS_API_PASSWORD: str = ""
    IFLYTEK_SMART_TTS_VOICE: str = "x6_lingxiaoxuan_flow"
    IFLYTEK_SMART_TTS_SPEED: int = 50
    IFLYTEK_SMART_TTS_VOLUME: int = 50
    IFLYTEK_SMART_TTS_PITCH: int = 50
    IFLYTEK_SMART_TTS_SAMPLE_RATE: int = 24000
    IFLYTEK_SMART_TTS_MAX_BYTES: int = 65536

    # --- Triage / RAG (Ollama + ChromaDB) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    OLLAMA_TIMEOUT: float = 120.0

    # --- LLM backend (OpenAI-compatible: Ollama / vLLM / Aliyun DashScope / ...) ---
    # Leave LLM_* empty to fall back to OLLAMA_* (local dev on Ollama).
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: float = 0.0  # 0 -> fall back to OLLAMA_TIMEOUT

    # --- Embedding backend (OpenAI-compatible) ---
    # Leave EMBED_* empty to fall back to OLLAMA_*.
    EMBED_BASE_URL: str = ""
    EMBED_API_KEY: str = ""
    EMBED_MODEL: str = ""
    EMBED_TIMEOUT: float = 0.0

    EMBEDDING_DIM: int = 1024
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION: str = "hospital_kb"
    KB_DIR: str = "./knowledge"
    TRIAGE_TOP_K: int = 4
    TRIAGE_MAX_HISTORY: int = 6
    TRIAGE_CHUNK_SIZE: int = 500
    TRIAGE_CHUNK_OVERLAP: int = 80


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
