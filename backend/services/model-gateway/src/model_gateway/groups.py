from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .adapters import (
    MockAdapter,
    ModelAdapter,
    NPUAdapter,
    OllamaAdapter,
    OpenAICompatAdapter,
)

GROUPS_FILE = Path(__file__).parent / "model_groups.yaml"


@lru_cache
def load_groups() -> dict[str, Any]:
    with open(GROUPS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def build_adapters() -> dict[str, ModelAdapter]:
    cfg = load_groups()
    adapters: dict[str, ModelAdapter] = {}
    for name, g in cfg.get("groups", {}).items():
        adapter_type = g.get("adapter")
        models = g.get("models") or []
        default_model = models[0] if models else None
        if adapter_type == "mock":
            adapters[name] = MockAdapter()
        elif adapter_type == "openai_compat":
            base_url = os.environ.get(g.get("base_url_env", ""), "")
            api_key = os.environ.get(g.get("api_key_env", ""), "")
            adapters[name] = OpenAICompatAdapter(
                base_url=base_url,
                api_key=api_key,
                default_model=default_model or "deepseek-chat",
            )
        elif adapter_type == "ollama":
            base_url = os.environ.get(g.get("base_url_env", ""), "http://localhost:11434")
            adapters[name] = OllamaAdapter(
                base_url=base_url,
                default_model=default_model or "qwen2.5-1.5b",
            )
        elif adapter_type == "npu":
            adapters[name] = NPUAdapter(model_path=default_model or "rknn-vlm-local")
    # 兜底保证 mock 存在
    if "skeleton_mock" not in adapters:
        adapters["skeleton_mock"] = MockAdapter()
    return adapters


def resolve_group(scene: str | None) -> str:
    cfg = load_groups()
    routes = cfg.get("scene_routes", {})
    return routes.get(scene or "", cfg.get("default_group", "skeleton_mock"))


def get_adapter(group: str | None) -> tuple[str, ModelAdapter]:
    """返回 (实际使用的 group 名, 适配器)。不可用则回退 skeleton_mock。"""
    adapters = build_adapters()
    target = group or resolve_group(None)
    adapter = adapters.get(target)
    if adapter is None or not _sync_available(adapter):
        return "skeleton_mock", adapters["skeleton_mock"]
    return target, adapter


def _sync_available(adapter: ModelAdapter) -> bool:
    """同步判断：仅看静态可 availability（mock=True，openai_compat 看是否有 key）。

    ollama 的 available 是异步探测，这里默认认为可尝试；真正的连通错误
    会在请求时抛出并被调用方捕获回退。
    """
    if adapter.name == "openai_compat":
        return bool(getattr(adapter, "api_key", ""))
    if adapter.name == "npu":
        return False
    return True
