"""机器人硬件抽象层（HAL）。"""

from .base import RobotDriver
from .registry import default_driver, get_driver, list_drivers, register_driver

__all__ = [
    "RobotDriver",
    "register_driver",
    "get_driver",
    "default_driver",
    "list_drivers",
]
