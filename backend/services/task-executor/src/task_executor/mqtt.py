from __future__ import annotations

import json
import logging
from typing import Any

import aiomqtt

from my_robot_common.settings import get_settings

logger = logging.getLogger("task_executor.mqtt")


def _client_kwargs() -> dict[str, Any]:
    settings = get_settings()
    return {
        "hostname": settings.emqx_host,
        "port": settings.emqx_port,
        "username": settings.emqx_username or None,
        "password": settings.emqx_password or None,
    }


async def publish_command(
    tenant_id: str, device_id: str, task_id: str, action: dict[str, Any], result: dict[str, Any]
) -> None:
    topic = f"robot/{tenant_id}/{device_id}/cmd"
    payload = json.dumps(
        {
            "id": task_id,
            "type": action.get("type"),
            "params": action.get("params") or {},
            "status": "done" if result.get("ok") else "failed",
            "result": result,
        },
        ensure_ascii=False,
    )
    try:
        async with aiomqtt.Client(**_client_kwargs()) as client:
            await client.publish(topic, payload=payload, qos=1)
        logger.info("已发布 MQTT cmd: %s", topic)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MQTT 发布失败（broker 不可用？）: %s", exc)


async def subscribe_state_forever() -> None:
    """订阅 robot/+/+/state 回执，记录日志。骨架阶段仅打日志。"""
    try:
        async with aiomqtt.Client(**_client_kwargs()) as client:
            await client.subscribe("robot/+/+/state")
            async for message in client.messages:
                try:
                    payload = message.payload.decode("utf-8")
                except (AttributeError, UnicodeDecodeError):
                    payload = str(message.payload)
                logger.info("收到设备状态回执 topic=%s payload=%s", message.topic, payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MQTT 订阅中断: %s", exc)
