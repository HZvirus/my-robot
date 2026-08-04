from __future__ import annotations

from typing import Any

from .base import Skill

_REGISTRY: dict[str, Skill] = {}


def register_skill(s: Skill) -> Skill:
    _REGISTRY[s.name] = s
    return s


def skill(name: str, description: str, args_schema: dict[str, Any] | None = None):
    """装饰器：把 async 函数注册为技能。"""

    def decorator(handler):
        register_skill(
            Skill(
                name=name,
                description=description,
                handler=handler,
                args_schema=args_schema or {},
            )
        )
        return handler

    return decorator


def get_skill(name: str) -> Skill:
    if name not in _REGISTRY:
        raise KeyError(f"未注册的技能: {name}; 已注册: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_skills() -> list[Skill]:
    return list(_REGISTRY.values())


async def call_skill(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return await get_skill(name).run(args)
