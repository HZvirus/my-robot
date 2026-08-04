from __future__ import annotations

from .base import RobotDriver
from .mock_driver import MockDriver

_REGISTRY: dict[str, RobotDriver] = {}


def register_driver(driver: RobotDriver) -> None:
    _REGISTRY[driver.name] = driver


def get_driver(name: str) -> RobotDriver:
    if name not in _REGISTRY:
        raise KeyError(f"未注册的驱动: {name}; 已注册: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_drivers() -> list[str]:
    return list(_REGISTRY)


def default_driver() -> RobotDriver:
    if "mock" not in _REGISTRY:
        register_driver(MockDriver())
    return get_driver("mock")


# 默认注册 mock 驱动，使导入即可用
register_driver(MockDriver())
