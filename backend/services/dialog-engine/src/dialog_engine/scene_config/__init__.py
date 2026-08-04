from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

SCENE_DIR = Path(__file__).parent
AVAILABLE_SCENES = ("hospital", "home")


class SceneConfig(BaseModel):
    name: str
    display_name: str = ""
    model_group: str = "skeleton_mock"
    rag_mode: Literal["force", "on_demand"] = "on_demand"
    rag_collections: list[str] = []
    asr_profile: str = "quiet"
    safety_policy: Literal["escalate", "soothe"] = "soothe"
    output_format: Literal["structured", "natural"] = "natural"
    max_tokens: int = 512
    system_prompt: str = ""


@lru_cache(maxsize=8)
def load_scene_config(name: str) -> SceneConfig:
    if name not in AVAILABLE_SCENES:
        raise KeyError(f"未知场景: {name}; 可用: {AVAILABLE_SCENES}")
    path = SCENE_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SceneConfig(**data)


def available_scenes() -> tuple[str, ...]:
    return AVAILABLE_SCENES
