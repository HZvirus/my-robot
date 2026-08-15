'''FastAPI application entry.'''

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes import auth, chat, companion, profile, smart_tts, triage, tts
from app.core.config import settings
from app.core.logger import setup_logging
from app.db.models import Conversation, Message, User  # noqa: F401 - register ORM models
from app.db.session import Base, engine


def _run_lightweight_migrations() -> None:
    '''Patch schema drift that create_all cannot handle (existing dev databases).

    create_all only creates missing tables; for an existing conversations table
    the owner_id column must be added manually (SQLite supports ADD COLUMN).
    '''
    with engine.begin() as conn:
        columns = {c['name'] for c in inspect(conn).get_columns('conversations')}
        if 'owner_id' not in columns:
            conn.execute(text('ALTER TABLE conversations ADD COLUMN owner_id VARCHAR(64)'))
            conn.execute(
                text(
                    'CREATE INDEX IF NOT EXISTS ix_conversations_owner_id '
                    'ON conversations (owner_id)'
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
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
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router, prefix='/api', tags=['auth'])
app.include_router(chat.router, prefix='/api', tags=['chat'])
app.include_router(companion.router, prefix='/api', tags=['companion'])
app.include_router(profile.router, prefix='/api', tags=['profile'])
app.include_router(triage.router, prefix='/api', tags=['triage'])
app.include_router(tts.router, prefix='/api', tags=['tts'])
app.include_router(smart_tts.router, prefix='/api', tags=['smart-tts'])


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}
