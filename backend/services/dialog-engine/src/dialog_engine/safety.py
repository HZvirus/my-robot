from __future__ import annotations

from typing import Any

# 高危关键词（医学/心理安全）
HIGH_RISK_WORDS = ["癌症", "肿瘤晚期", "死亡", "自杀", "不想活", "抑郁", "绝症"]

SOOTHE_MESSAGE = (
    "听起来这件事让您有些担心，别着急，我们慢慢说，我会一直陪着您。"
    "如果您觉得很不舒服，建议联系家人或医生聊聊。"
)
ESCALATE_MESSAGE = "检测到高风险关键词，已通知值班人员关注，请保持冷静。"


def check_safety(text: str, policy: str) -> dict[str, Any] | None:
    """检测高危词并按场景策略返回事件。"""
    hit = [w for w in HIGH_RISK_WORDS if w in text]
    if not hit:
        return None
    if policy == "escalate":
        return {
            "event": "escalate",
            "hit": hit,
            "message": ESCALATE_MESSAGE,
        }
    return {
        "event": "soothe",
        "hit": hit,
        "message": SOOTHE_MESSAGE,
    }
