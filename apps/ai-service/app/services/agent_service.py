"""Agent 业务服务：编排"一次问答"的完整生命周期。

``AgentService`` 把各模块串成一条端到端流水线：

1. 确定会话 ID（复用传入的，或新建 UUID）
2. 校验/创建会话归属（ConversationContext.ensure）
3. 加载历史消息（供模型做上下文）
4. 运行 ReAct 循环（AgentRunner.run，内部调用 LLM 与工具）
5. 持久化本轮问答与推理足迹（ConversationContext）
6. 组装并返回 AgentRunResponse（DTO）

因为 SQLAlchemy 是同步的，所有数据库调用都经 ``anyio.to_thread``
放到线程池执行，避免阻塞事件循环。
"""

from __future__ import annotations

from functools import partial
from uuid import uuid4

from anyio import to_thread
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.agent import AgentRunResponse, AgentStepOut
from app.services.agent.agent import AgentRunner
from app.services.agent.context import ConversationContext
from app.services.llm_client import OpenAICompatClient


class AgentService:
    """Agent 业务服务。

    注入 LLM 客户端与 session 工厂即可使用；默认实例 ``agent_service``
    使用全局单例 llm_client 与 SessionLocal。

    端到端示例（可离线执行：内存 SQLite + 假 LLM 客户端）：
    >>> import asyncio
    >>> from sqlalchemy import create_engine
    >>> from sqlalchemy.pool import StaticPool
    >>> from sqlalchemy.orm import sessionmaker
    >>> from app.db.models import Base

    # 1) 建内存库与假客户端（永远返回纯文本，不调用工具）
    >>> engine = create_engine(
    ...     "sqlite://", connect_args={"check_same_thread": False},
    ...     poolclass=StaticPool)
    >>> Base.metadata.create_all(engine)
    >>> sf = sessionmaker(bind=engine)

    >>> class PlainClient:
    ...     async def chat_complete(self, messages, **kwargs):
    ...         return {"role": "assistant",
    ...                 "content": "现在时刻是 2026-08-21T12:00:00+00:00"}

    # 2) 运行一次问答：模型直接回答，无工具调用，无推理足迹
    >>> svc = AgentService(PlainClient(), sf)
    >>> resp = asyncio.run(svc.run("现在几点?", "conv-1", "user-a"))
    >>> resp.answer
    '现在时刻是 2026-08-21T12:00:00+00:00'
    >>> resp.conversation_id
    'conv-1'
    >>> resp.steps
    []
    >>> resp.model_dump(by_alias=True)
    {'conversationId': 'conv-1', 'answer': '现在时刻是 2026-08-21T12:00:00+00:00', 'steps': []}

    # 3) 本轮问答已持久化，可被再次加载为上下文
    >>> from app.services.agent.context import ConversationContext
    >>> ConversationContext(sf).load_history("conv-1", 10)
    [{'role': 'user', 'content': '现在几点?'}, {'role': 'assistant', 'content': '现在时刻是 2026-08-21T12:00:00+00:00'}]

    # 4) 若模型第一轮要求调用工具，则产生一条推理足迹
    >>> class ToolClient:
    ...     def __init__(self):
    ...         self.calls = 0
    ...     async def chat_complete(self, messages, **kwargs):
    ...         self.calls += 1
    ...         if self.calls == 1:
    ...             return {"role": "assistant", "content": "让我查一下时间",
    ...                     "tool_calls": [{"id": "c1", "type": "function",
    ...                                     "function": {"name": "get_current_time",
    ...                                                  "arguments": "{}"}}]}
    ...         return {"role": "assistant", "content": "时间是 20:00"}
    >>> svc2 = AgentService(ToolClient(), sf)
    >>> resp2 = asyncio.run(svc2.run("现在几点?", "conv-2", "user-a"))
    >>> resp2.answer
    '时间是 20:00'
    >>> resp2.steps[0].step_no
    0
    >>> resp2.steps[0].action
    '{"tool": "get_current_time", "args": {}}'

    # 5) 足迹持久化后可查询；非属主查询被拒绝
    >>> svc2.list_steps("conv-2", "user-a")[0].status
    'done'
    >>> try:
    ...     svc2.list_steps("conv-2", "user-b")
    ... except Exception as exc:
    ...     type(exc).__name__
    'KeyError'
    """

    def __init__(
            self,
            client: OpenAICompatClient,
            session_factory: sessionmaker[Session],
    ) -> None:
        """注入依赖。

        - client           LLM 客户端（如全局单例 llm_client）
        - session_factory  SQLAlchemy 会话工厂（如 SessionLocal）
        """
        self._client = client
        self._ctx = ConversationContext(session_factory)
        self._runner = AgentRunner(client=client)

    async def run(
            self, message: str, conversation_id: str | None, owner_id: str
    ) -> AgentRunResponse:
        """执行一次完整问答并持久化。

        输入：
        - message         用户提问文本
        - conversation_id 会话 ID；None 时自动生成新 UUID（开启新会话）
        - owner_id        会话属主（用于归属校验/防越权）

        输出：AgentRunResponse
        - conversation_id  实际使用的会话 ID（新会话时为新建 UUID）
        - answer           最终答案文本
        - steps            推理足迹（AgentStepOut 列表，可直接渲染）

        流程：ensure 归属 -> load_history -> runner.run -> 持久化问答
        -> 持久化足迹 -> 组装响应。其中 LLM 循环在 runner 内完成。

        注意：这是异步方法；内部所有 DB 调用经 to_thread 在线程池执行。
        端到端示例见类 docstring（conv-1 直接回答 / conv-2 调用工具两条路径）。
        """
        # 1) 会话 ID：复用传入值，否则新建（返回给前端即新会话标识）
        conv_id = conversation_id or str(uuid4())
        # 2) 校验/创建会话归属（线程池内同步执行）
        await to_thread.run_sync(partial(self._ctx.ensure, conv_id, owner_id))

        # 3) 加载最近历史消息，作为模型上下文
        history = await to_thread.run_sync(
            self._ctx.load_history, conv_id, settings.COMPANION_MAX_HISTORY
        )

        # 4) 运行 ReAct 循环，得到最终答案与足迹
        answer, steps = await self._runner.run(message, history)

        # 5) 持久化本轮问答（user + assistant 两条消息）
        await to_thread.run_sync(
            partial(self._ctx.persist_user_and_assistant, conv_id, message, answer)
        )

        # 6) 持久化每一条推理足迹
        for step in steps:
            await to_thread.run_sync(partial(self._ctx.persist_step, conv_id, step))

        # 7) 组装 DTO 响应（action 用 action_json 序列化的工具+参数）
        return AgentRunResponse(
            conversation_id=conv_id,
            answer=answer,
            steps=[
                AgentStepOut(
                    step_no=s.step_no,
                    thought=s.thought,
                    action=s.action_json(),
                    observation=s.observation,
                    status=s.status)
                for s in steps
            ]
        )

    def list_steps(self, conversation_id: str, owner_id: str) -> list[AgentStepOut]:
        """查询某会话的推理足迹（仅属主可见）。

        输入：
        - conversation_id  会话 ID
        - owner_id         请求者身份

        输出：AgentStepOut 列表（按 step_no 升序）；
        会话不存在或归属不符时抛 KeyError（由 ensure_access 抛出）。

        输入输出示例：
        - 属主查询  -> 返回足迹列表（见类 docstring 第 5 步）
        - 非属主查询 -> KeyError（见类 docstring 第 5 步）

        注意：这里遍历的是 AgentStep ORM 对象，action 字段本身已是
        持久化好的 JSON 字符串（{"tool","args"}），直接透传即可。
        """
        self._ctx.ensure_access(conversation_id, owner_id)
        return [
            AgentStepOut(
                step_no=s.step_no,
                thought=s.thought,
                action=s.action,
                observation=s.observation,
                status=s.status)
            for s in self._ctx.list_steps(conversation_id)
        ]


def _build_default_service() -> AgentService:
    """用全局单例构建默认服务实例（llm_client + SessionLocal）。"""
    from app.db.session import SessionLocal
    from app.services.llm_client import llm_client
    return AgentService(
        llm_client, SessionLocal
    )


# 全局共享的默认服务实例，API 路由直接使用
agent_service = _build_default_service()
