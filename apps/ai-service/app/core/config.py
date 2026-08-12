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

    AI_API_KEY: str = ""
    AI_API_BASE: str = ""
    AI_MODEL: str = "gpt-4o-mini"

    DATABASE_URL: str = "sqlite:///./app.db"

    # --- General chat (streaming, context-aware) ---
    CHAT_MAX_HISTORY: int = 10

    # --- Companion (health companionship chat, streaming) ---
    COMPANION_MAX_HISTORY: int = 12

    # --- Triage / RAG (Ollama + ChromaDB) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    OLLAMA_TIMEOUT: float = 120.0
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
