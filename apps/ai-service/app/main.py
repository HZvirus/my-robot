from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, companion, profile, triage, tts
from app.core.config import settings
from app.core.logger import setup_logging
from app.db.models import Conversation, Message  # noqa: F401 - register ORM models
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(companion.router, prefix="/api", tags=["companion"])
app.include_router(profile.router, prefix="/api", tags=["profile"])
app.include_router(triage.router, prefix="/api", tags=["triage"])
app.include_router(tts.router, prefix="/api", tags=["tts"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
