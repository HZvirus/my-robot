from __future__ import annotations

from .base import ChatMessage, ChatRequest, ModelAdapter
from .mock import MockAdapter
from .npu import NPUAdapter
from .ollama import OllamaAdapter
from .openai_compat import OpenAICompatAdapter

__all__ = [
    "ChatRequest",
    "ChatMessage",
    "ModelAdapter",
    "MockAdapter",
    "OpenAICompatAdapter",
    "OllamaAdapter",
    "NPUAdapter",
]
