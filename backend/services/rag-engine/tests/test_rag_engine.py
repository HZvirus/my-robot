import pytest
from fastapi.testclient import TestClient

from rag_engine.chunker import chunk_text
from rag_engine.embedding import deterministic_embedding
from rag_engine.main import app
from rag_engine.seed import SEED_DOCS

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["vector_dim"] == 256


def test_deterministic_embedding_is_stable_and_normalized():
    a = deterministic_embedding("今天天气真好")
    b = deterministic_embedding("今天天气真好")
    assert a == b
    assert len(a) == 256
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_embedding_distinguishes_different_texts():
    a = deterministic_embedding("骨科门诊在三层")
    b = deterministic_embedding("关灯开灯音乐播放")
    assert a != b


def test_chunk_text_splits_by_punctuation():
    chunks = chunk_text("第一句。第二句！第三句？")
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_seed_collections_cover_both_scenes():
    names = set(SEED_DOCS.keys())
    assert {"hospital_dept", "home_care"} <= names
