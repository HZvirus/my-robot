from __future__ import annotations

import re


def chunk_text(text: str, size: int = 200, overlap: int = 20) -> list[str]:
    """按句末标点切分，尽量不超过 size 字符，保留 overlap 上下文。"""
    sentences = re.split(r"(?<=[。！？!?；;\n])", text)
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if buf and len(buf) + len(s) > size:
            chunks.append(buf)
            buf = buf[-overlap:] if overlap else ""
        buf += s
    if buf.strip():
        chunks.append(buf)
    return chunks or [text.strip()]
