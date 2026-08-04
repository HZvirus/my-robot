from __future__ import annotations

import hashlib
import math
import re

from .db import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """离线确定性 embedding：基于 token 哈希的稀疏归一化向量。

    - 同一文本恒定输出同一向量（可复现）
    - 不依赖任何外部模型，骨架阶段可跑通检索链路
    - 预留接口供后续替换为 sentence-transformers provider
    """
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
        # 二阶特征：双字组合
    bi_tokens = ["-".join(pair) for pair in zip(tokenize(text), tokenize(text)[1:])]
    for tok in bi_tokens:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
