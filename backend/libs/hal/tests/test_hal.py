import pytest

from my_robot_hal import default_driver, get_driver, list_drivers
from my_robot_hal.ubt_driver import UBTDriver


@pytest.mark.asyncio
async def test_mock_driver_executes_and_logs():
    driver = default_driver()
    result = await driver.execute({"type": "speak", "params": {"text": "你好"}})
    assert result["ok"] is True
    assert result["action"] == "speak"
    status = await driver.status()
    assert status["online"] is True


@pytest.mark.asyncio
async def test_semantic_method_routes_to_execute():
    driver = get_driver("mock")
    result = await driver.move_forward(distance=1.0)
    assert result["action"] == "move_forward"
    assert result["params"]["distance"] == 1.0


@pytest.mark.asyncio
async def test_ubt_driver_is_placeholder():
    ubt = UBTDriver()
    assert ubt.name == "ubt"
    assert await ubt.available() is False
    with pytest.raises(NotImplementedError):
        await ubt.execute({"type": "move_forward", "params": {}})


def test_registry_lists_mock():
    assert "mock" in list_drivers()
