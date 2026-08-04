"""技能插件骨架。"""

from .base import Skill
from .registry import call_skill, get_skill, list_skills, register_skill, skill

# 导入示例技能以完成注册
from .examples import get_dept_schedule, weather_broadcast  # noqa: F401,E402

__all__ = [
    "Skill",
    "skill",
    "register_skill",
    "get_skill",
    "list_skills",
    "call_skill",
]
