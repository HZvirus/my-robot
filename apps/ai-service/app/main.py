"""FastAPI application entry."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent,auth, companion, smart_tts
from app.core.config import settings
from app.core.logger import setup_logging
from app.db.models import AgentStep,Conversation, Message, User  # noqa: F401 - register ORM models
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

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(companion.router, prefix="/api", tags=["companion"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(smart_tts.router, prefix="/api", tags=["smart-tts"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
