import pytest

from my_robot_skills import call_skill, list_skills


def test_skills_registered():
    names = {s.name for s in list_skills()}
    assert {"get_dept_schedule", "weather_broadcast"} <= names


@pytest.mark.asyncio
async def test_call_stub_skill():
    result = await call_skill("weather_broadcast", {"city": "北京"})
    assert result["ok"] is True
    assert "北京" in result["text"]


@pytest.mark.asyncio
async def test_unknown_skill_raises():
    with pytest.raises(KeyError):
        await call_skill("nope")
