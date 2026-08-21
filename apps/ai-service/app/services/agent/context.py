"""Agent 会话上下文：把 ReAct 循环与数据库持久化对接。

本模块提供 ``ConversationContext``，负责一个会话的全部数据库操作：

- ensure / ensure_access   会话归属校验（创建 or 鉴权）
- load_history             加载历史消息（喂给 agent 做上下文）
- persist_user_and_assistant  保存一轮问答（user + assistant 两条消息）
- persist_step / list_steps   保存 / 查询 ReAct 足迹（AgentStep）

设计要点：
- 每个方法用 `_scope()` 开一个独立短会话，用完即关，天然隔离事务；
- 读写都是同步操作，异步调用方应通过 `asyncio.to_thread` 调用。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AgentStep, Conversation, Message
from app.services.agent.state import StepRecord


class ConversationContext:
    """会话持久化上下文：基于 SQLAlchemy session_factory 封装库操作。

    使用前需提供绑定好数据库的 ``sessionmaker``（如 ``app.db.session.SessionLocal``）。

    端到端示例（全部方法均可离线执行，使用共享内存的 SQLite）：
    >>> from sqlalchemy import create_engine
    >>> from sqlalchemy.pool import StaticPool
    >>> from app.db.models import Base
    >>> engine = create_engine(
    ...     "sqlite://", connect_args={"check_same_thread": False},
    ...     poolclass=StaticPool)  # 多连接共享同一内存库
    >>> Base.metadata.create_all(engine)
    >>> cc = ConversationContext(sessionmaker(bind=engine))

    归属校验：
    >>> cc.ensure("conv-1", "user-a")          # 会话不存在 -> 自动创建
    >>> cc.ensure("conv-1", "user-a")          # 已存在且归属正确 -> 不报错
    >>> cc.ensure("conv-1", "user-b")          # 归属不符 -> 抛 PermissionError
    Traceback (most recent call last):
        ...
    PermissionError: Conversation conv-1 does not belong to owner user-b

    鉴权式校验（ensure_access，比 ensure 更严格，不自动创建）：
    >>> cc.ensure_access("conv-1", "user-a")   # 存在且归属正确 -> 通过
    >>> cc.ensure_access("nope", "user-a")     # 不存在 -> 抛 KeyError
    Traceback (most recent call last):
        ...
    KeyError: 'Conversation nope does not belong to owner user-a'

    保存一轮问答，再加载历史：
    >>> cc.persist_user_and_assistant("conv-1", "现在几点?", "现在是 20:00")
    >>> cc.load_history("conv-1", limit=10)
    [{'role': 'user', 'content': '现在几点?'}, {'role': 'assistant', 'content': '现在是 20:00'}]

    保存并查询 ReAct 足迹：
    >>> cc.persist_step("conv-1", StepRecord(
    ...     step_no=0, thought="用户问时间,先取当前时间",
    ...     tool_name="get_current_time", tool_args={}, observation='"20:00"'))
    >>> steps = cc.list_steps("conv-1")
    >>> [(s.step_no, s.action, s.observation) for s in steps]
    [(0, '{"tool": "get_current_time", "args": {}}', '"20:00"')]
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """注入 session 工厂（通常传 app.db.session.SessionLocal）。"""
        self._sf = session_factory

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        """打开一个用完即关的数据库会话（contextmanager）。

        每个操作独立开会话：提交后关闭，下次操作再开新的，
        避免长生命周期会话带来的连接占用与脏状态。
        """
        db = self._sf()
        try:
            yield db
        finally:
            db.close()

    def ensure(self, conv_id: str, owner_id: str) -> None:
        """确保会话存在且归属 owner_id。

        - 会话不存在 -> 自动创建（owner_id 记为该会话属主）
        - 会话存在但归属他人 -> 抛 PermissionError（防越权）
        - 会话存在且归属正确 -> 什么都不做

        用于开始新会话时：先创建（或复用）会话再继续写消息。
        输入输出示例见类 docstring（conv-1 / user-a / user-b 场景）。
        """
        with self._scope() as db:
            conv = db.get(Conversation, conv_id)
            if conv is None:
                db.add(Conversation(id=conv_id, owner_id=owner_id))
                db.commit()
            elif conv.owner_id != owner_id:
                raise PermissionError(f"Conversation {conv_id} does not belong to owner {owner_id}")

    def ensure_access(self, conv_id: str, owner_id: str) -> None:
        """严格鉴权：会话必须存在且归属 owner_id，否则抛 KeyError。

        与 ensure 的区别：**不自动创建**。用于后续轮次访问历史会话，
        保证只有属主才能读取/续写。输入输出示例见类 docstring。
        """
        with self._scope() as db:
            conv = db.get(Conversation, conv_id)
            if conv is None or conv.owner_id != owner_id:
                raise KeyError(f"Conversation {conv_id} does not belong to owner {owner_id}")

    def load_history(self, conv_id: str, limit: int) -> list[dict]:
        """加载指定会话最近 limit 条消息，按时间升序（旧 -> 新）。

        输入：
        - conv_id  会话 ID
        - limit    最多返回多少条（取"最近 N 条"）

        输出：OpenAI 兼容消息字典列表，如
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        顺序为时间升序，可直接拼接进 messages 上下文。

        实现说明：先按 created_at 倒序取最近 limit 条，再反转成升序。
        """
        with self._scope() as db:
            rows = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                ).all()
            )
            rows.reverse()
            return [{"role": r.role, "content": r.content} for r in rows]

    def persist_user_and_assistant(self, conv_id: str, user_message: str, assistant_text: str) -> None:
        """保存一轮问答：写入 user 消息 + assistant 消息各一条。

        输入：
        - conv_id         会话 ID
        - user_message    用户提问文本
        - assistant_text  AI 回复文本

        细节：
        - 两条消息 created_at 差 1 微秒，保证加载历史时顺序稳定为 先 user 后 assistant；
        - 主键用 uuid4() 生成；interrupted 一律 False（本函数只存完整回复）。
        """
        with self._scope() as db:
            now = datetime.now(UTC).replace(tzinfo=None)
            db.add(
                Message(id=str(uuid4()), conversation_id=conv_id, role="user", content=user_message, interrupted=False, created_at=now)
            )
            db.add(
                Message(id=str(uuid4()), conversation_id=conv_id, role="assistant", content=assistant_text, interrupted=False, created_at=now + timedelta(microseconds=1))
            )
            db.commit()

    def persist_step(self, conv_id: str, step: StepRecord) -> None:
        """把一轮 ReAct 足迹持久化为一条 AgentStep 记录。

        输入：
        - conv_id  会话 ID
        - step     StepRecord（state.py 中的足迹对象）

        字段映射（StepRecord -> AgentStep 列）：
        - step_no       -> step_no
        - thought       -> thought
        - tool_name     -> action  （用 action_json() 序列化成 {"tool","args"} JSON 字符串存储）
        - observation   -> observation
        - status        -> status
        """
        with self._scope() as db:
            now = datetime.now(UTC).replace(tzinfo=None)
            db.add(
                AgentStep(
                    id=str(uuid4()),
                    conversation_id=conv_id,
                    step_no=step.step_no,
                    thought=step.thought,
                    action=step.action_json(),
                    observation=step.observation,
                    status=step.status,
                )
            )
            db.commit()

    def list_steps(self, conv_id: str) -> list[AgentStep]:
        """按 step_no 升序返回会话的全部足迹（AgentStep ORM 对象列表）。

        输出：AgentStep 列表，每项含 step_no / thought / action /
        observation / status 等字段，前端可直接渲染"AI 推理过程"。
        """
        with self._scope() as db:
            rows = list(
                db.scalars(
                    select(AgentStep)
                    .where(AgentStep.conversation_id == conv_id)
                    .order_by(AgentStep.step_no.asc())
                ).all()
            )
            return rows
