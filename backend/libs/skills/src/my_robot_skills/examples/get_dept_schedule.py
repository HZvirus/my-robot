from __future__ import annotations

from typing import Any

from ..registry import skill


@skill(
    name="get_dept_schedule",
    description="查询医院科室排班/出诊信息（stub）",
    args_schema={"dept": "string"},
)
async def get_dept_schedule(args: dict[str, Any]) -> dict[str, Any]:
    dept = args.get("dept", "全科")
    return {
        "ok": True,
        "dept": dept,
        "schedule": [
            {"doctor": "李医生", "time": "周一至周五 09:00-12:00"},
            {"doctor": "王医生", "time": "周二、周四 14:00-17:00"},
        ],
        "note": "骨架 stub 返回示例排班，未接入真实排班系统",
    }
