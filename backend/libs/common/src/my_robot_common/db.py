from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str | None = None) -> None:
    """初始化引擎与会话工厂（仅创建对象，不连接）。"""
    global _engine, _session_maker
    from .settings import get_settings

    settings = get_settings()
    _engine = create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
        future=True,
    )
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def close_db() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        raise RuntimeError("DB 未初始化，请先调用 init_db()")
    return _session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每请求一个 session。"""
    maker = get_session_maker()
    async with maker() as session:
        yield session


async def create_tables(base: type[DeclarativeBase]) -> None:
    """在当前引擎上创建 base.metadata 中的所有表（已存在则跳过）。"""
    if _engine is None:
        await init_db()
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)


async def enable_pgvector() -> None:
    """创建 pgvector 扩展（仅 rag-engine 需要）。"""
    if _engine is None:
        await init_db()
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


async def execute_text(sql: str, params: dict[str, Any] | None = None) -> Any:
    """便捷工具：执行原始 SQL。"""
    if _engine is None:
        await init_db()
    assert _engine is not None
    async with _engine.begin() as conn:
        return await conn.execute(text(sql), params or {})
