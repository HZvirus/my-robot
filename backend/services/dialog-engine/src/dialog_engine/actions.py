from __future__ import annotations

import json
from uuid import uuid4
from typing import Any


def _find_first_json_object(text: str) -> str | None:
    """扫描文本，返回第一个含 "type" 的平衡 JSON 对象子串（支持嵌套大括号）。"""
    for start in (i for i, c in enumerate(text) if c == "{"):
        depth = 0
        for j in range(start, len(text)):
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : j + 1]
                    if '"type"' in candidate:
                        return candidate
                    break
    return None


def extract_action(text: str) -> dict[str, Any] | None:
    """从助手回复中提取结构化动作 JSON，失败返回 None（降级纯文本）。

    支持裸 JSON 与 ```json 围栏，均通过平衡大括号扫描，兼容嵌套 params。
    """
    candidate = _find_first_json_object(text)
    if candidate is None:
        return None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("type"):
        return None
    return {
        "id": data.get("id") or uuid4().hex,
        "type": data["type"],
        "params": data.get("params") or {},
    }
