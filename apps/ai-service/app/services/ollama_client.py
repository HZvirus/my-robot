"""Backward-compatible re-exports.

The real implementation lives in :mod:`app.services.llm_client`, an
OpenAI-compatible client that talks to Ollama, vLLM or hosted APIs (DashScope
etc.). This module keeps the historical names (``OllamaClient``, ``ollama_client``)
so existing imports keep working; new code should import ``llm_client`` /
``embed_client`` directly.
"""

from app.services.llm_client import (
    OpenAICompatClient as OpenAICompatClient,
)
from app.services.llm_client import (
    embed_client as embed_client,
)
from app.services.llm_client import (
    llm_client as llm_client,
)

# Historical aliases kept for backward compatibility.
OllamaClient = OpenAICompatClient
ollama_client = llm_client

__all__ = [
    "OpenAICompatClient",
    "OllamaClient",
    "embed_client",
    "llm_client",
    "ollama_client",
]
