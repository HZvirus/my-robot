from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import aiomqtt

from my_robot_common.settings import get_settings

logger = logging.getLogger("mock_robot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [mock-robot] %(message)s")


def _client_kwargs() -> dict[str, Any]:
    settings = get_settings()
    return {
        "hostname": settings.emqx_host,
        "port": settings.emqx_port,
        "username": settings.emqx_username or None,
        "password": settings.emqx_password or None,
    }


async def run() -> None:
    settings = get_settings()
    cmd_topic = "robot/+/+/cmd"
    logger.info("mock-robot 启动，订阅 %s @ %s:%s", cmd_topic, settings.emqx_host, settings.emqx_port)
    retry = 0
    while True:
        try:
            async with aiomqtt.Client(**_client_kwargs()) as client:
                await client.subscribe(cmd_topic)
                retry = 0
                async for message in client.messages:
                    topic = str(message.topic)
                    try:
                        payload = json.loads(message.payload.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        payload = {"raw": str(message.payload)}
                    logger.info("收到指令 topic=%s payload=%s", topic, payload)
                    # 回执状态
                    state_topic = topic.rstrip("/cmd") + "/state"
                    await client.publish(
                        state_topic,
                        payload=json.dumps(
                            {"id": payload.get("id"), "status": "executed", "echo": payload},
                            ensure_ascii=False,
                        ),
                        qos=1,
                    )
                    logger.info("已回执 %s", state_topic)
        except Exception as exc:  # noqa: BLE001
            retry += 1
            delay = min(30, 2 ** retry)
            logger.warning("MQTT 连接异常，%ss 后重试: %s", delay, exc)
            await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(run())
