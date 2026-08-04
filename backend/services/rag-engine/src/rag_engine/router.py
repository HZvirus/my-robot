from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from my_robot_common.db import get_db
from my_robot_common.exceptions import AppException

from .chunker import chunk_text
from .db import Collection, Document
from .embedding import deterministic_embedding

router = APIRouter()


class CollectionIn(BaseModel):
    name: str
    description: str = ""


class CollectionOut(BaseModel):
    id: str
    name: str
    description: str


class DocumentIn(BaseModel):
    collection: str
    text: str
    metadata: dict = {}


class RetrieveIn(BaseModel):
    collection: str
    query: str
    top_k: int = 3


class RetrieveResult(BaseModel):
    text: str
    metadata: dict
    score: float


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(
    body: CollectionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CollectionOut:
    existing = await db.scalar(select(Collection).where(Collection.name == body.name))
    if existing is not None:
        raise AppException(409, "collection_exists", "集合名已存在")
    col = Collection(name=body.name, description=body.description)
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return CollectionOut(id=col.id, name=col.name, description=col.description)


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CollectionOut]:
    rows = await db.scalars(select(Collection).order_by(Collection.created_at))
    return [CollectionOut(id=c.id, name=c.name, description=c.description) for c in rows]


@router.post("/documents", status_code=201)
async def create_document(
    body: DocumentIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    col = await db.scalar(select(Collection).where(Collection.name == body.collection))
    if col is None:
        raise AppException(404, "collection_not_found", f"集合不存在: {body.collection}")
    chunks = chunk_text(body.text)
    ids: list[str] = []
    for i, ch in enumerate(chunks):
        doc = Document(
            collection_id=col.id,
            chunk=ch,
            embedding=deterministic_embedding(ch),
            meta={**body.metadata, "index": i, "chunks": len(chunks)},
        )
        db.add(doc)
        await db.flush()
        ids.append(doc.id)
    await db.commit()
    return {"ids": ids, "chunks": len(chunks), "collection": body.collection}


@router.post("/retrieve")
async def retrieve(
    body: RetrieveIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    col = await db.scalar(select(Collection).where(Collection.name == body.collection))
    if col is None:
        return {"collection": body.collection, "results": []}
    qvec = deterministic_embedding(body.query)
    distance = Document.embedding.cosine_distance(qvec).label("distance")
    stmt = (
        select(Document.chunk, Document.meta, distance)
        .where(Document.collection_id == col.id)
        .order_by(distance)
        .limit(max(1, min(body.top_k, 20)))
    )
    rows = (await db.execute(stmt)).all()
    results = [
        RetrieveResult(text=chunk, metadata=meta or {}, score=float(1.0 - dist))
        for chunk, meta, dist in rows
    ]
    return {"collection": body.collection, "results": [r.model_dump() for r in results]}


async def health_extra() -> dict:
    return {"vector_dim": 256, "embedding": "deterministic", "provider": "offline"}
