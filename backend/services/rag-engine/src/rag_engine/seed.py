from __future__ import annotations

import logging

from sqlalchemy import func, select

from my_robot_common.db import get_session_maker

from .chunker import chunk_text
from .db import Collection, Document
from .embedding import deterministic_embedding

logger = logging.getLogger("rag_engine.seed")

SEED_DOCS: dict[str, list[str]] = {
    "hospital_dept": [
        "骨科位于门诊楼三层，周一至周五全天门诊，急诊24小时接诊。",
        "内科设高血压、糖尿病专科门诊，建议提前在自助机预约挂号。",
        "急诊科位于一楼东侧，胸痛、卒中患者可直接走绿色通道优先处置。",
    ],
    "drug_manual": [
        "二甲双胍应随餐服用，常见不良反应为胃肠道反应，肾功能不全者慎用。",
        "阿莫西林为青霉素类抗生素，使用前需询问过敏史，疗程需足量。",
    ],
    "insurance_policy": [
        "本地医保门诊起付线500元，超过部分按比例报销，具体比例见医院公示。",
        "住院费用出院时医保直接结算，自付部分可用手机支付或窗口缴费。",
    ],
    "elder_health": [
        "老年人建议每日饮水1500毫升，适量运动，定期监测血压血糖。",
        "独居老人应保持与家属定期通话，出现胸闷、头晕应及时就医。",
    ],
    "home_care": [
        "居家照护应保持地面干燥防滑，卫生间安装扶手，夜间留小夜灯。",
        "提醒老人按时服药，药盒分装早中晚，避免漏服或重复服用。",
    ],
}


async def seed_if_empty() -> bool:
    maker = get_session_maker()
    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(Collection))
        if count:
            return False
        for name, docs in SEED_DOCS.items():
            col = Collection(name=name, description=f"{name} 示例知识库")
            session.add(col)
            await session.flush()
            for text in docs:
                for ch in chunk_text(text):
                    session.add(
                        Document(
                            collection_id=col.id,
                            chunk=ch,
                            embedding=deterministic_embedding(ch),
                            metadata={"source": "seed"},
                        )
                    )
        await session.commit()
        logger.info("RAG 种子数据已写入：%d 个集合", len(SEED_DOCS))
        return True
