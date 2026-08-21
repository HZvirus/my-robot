"""Agent 主循环：驱动 ReAct 流程（推理 → 调工具 → 观察 → 再推理）。

本模块是 agent 循环的调度核心，串起其它模块：

- planner.build_message   组装初始消息（system + history + user）
- state.AgentState       持有消息历史与步骤足迹，每轮回传给模型
- state.parse_assistant_message  解析 LLM 回复
- tools.ToolRegistry     工具注册表：schema 喂给模型、invoke 执行工具
- llm_client             实际调用 OpenAI 兼容后端

循环流程（简化版 ReAct）：
1. 把当前消息历史发给 LLM（携带工具 schema）
2. 解析回复：若**不请求工具** → 本轮结束，取 content 作为最终答案
3. 若**请求工具** → 逐个执行工具，把结果（role=tool）回填消息历史，
   记录一条 StepRecord，step_no+1，回到第 1 步继续
4. 超过 max_steps 仍未给出最终答案 → 强制让模型直接回答一次兜底
"""

from __future__ import annotations

import logging

from app.services.agent.planner import build_message
from app.services.agent.state import (
    AgentState,
    StepRecord,
    parse_assistant_message,
)

from app.services.agent.tools import ToolRegistry, default_registry
from app.services.llm_client import OpenAICompatClient

logger = logging.getLogger(__name__)

# 单个会话最多允许的 ReAct 轮数（防模型陷入无限工具循环）
DEFAULT_MAX_STEPS = 6


class AgentRunner:
    """Agent 执行器：把 LLM + 工具注册表 + 步数上限组合成一个 ReAct 循环。

    输入输出总览（run 方法）：
    - 输入: user_message 用户提问；history 历史对话（OpenAI 兼容字典列表）
    - 输出: (final_answer, steps)，其中
        * final_answer  最终答案文本
        * steps         推理过程足迹（StepRecord 列表，可落库展示）

    一次典型执行（最终答案轮无工具调用）：
    >>> # 说明：run 依赖真实 LLM 后端，无法离线执行，以下仅为数据流示例。
    >>> # 若 LLM 第一轮直接返回纯文本，则 steps 为空、final_answer 即该文本；
    >>> # 若 LLM 先调用 get_current_time，则会生成一条 StepRecord:
    >>> #   StepRecord(step_no=0, thought="用户问时间,先取当前时间",
    >>> #              tool_name="get_current_time", tool_args={},
    >>> #              observation='"2026-08-21T12:00:00+00:00"', status="done")
    """

    def __init__(
            self,
            client: OpenAICompatClient,
            tools: ToolRegistry | None = None,
            max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        """初始化执行器。

        - client      LLM 客户端（必须提供，通常传全局单例 llm_client）
        - tools       工具注册表；缺省用 default_registry（内置时间/计算器）
        - max_steps   最大 ReAct 轮数，防止死循环
        """
        self._client = client
        self._tools = tools or default_registry
        self._max_steps = max_steps

    async def run(self, user_message: str, history: list[dict]) -> tuple[str, list[StepRecord]]:
        """执行一次完整的 ReAct 循环，返回 (最终答案, 推理步骤列表)。

        ReAct 循环体：
        - 每轮携带 tools schema 请求 LLM（模型可自主决定是否调用工具）
        - 不请求工具 => 命中最终答案，跳出循环
        - 请求工具   => 逐个执行并回填结果，继续下一轮

        步数保护：
        - 若耗尽 max_steps 仍无最终答案，再强制发起一次不带工具的请求，
          让模型直接给出结论；仍无文本则返回兜底提示文案。
        """
        # 初始消息：system + history + 当前提问
        state = AgentState(messages=build_message(history, user_message))
        final_answer = ''
        answered = False

        while state.step_no < self._max_steps:
            # 1) 请求 LLM：带上工具 schema，让模型决定是否调用工具
            raw = await self._client.chat_complete(
                state.messages, tools=self._tools.schema()
            )
            # 2) 解析回复（含容错：content 缺省、arguments 坏 JSON 等）
            reply = parse_assistant_message(raw)
            # 3) 回复先进入消息历史，保证上下文连续
            state.add_assistant(reply)

            # 4) 不请求工具 => 本轮就是最终答案
            if not reply.wants_tool:
                final_answer = reply.content
                answered = True
                break

            # 5) 请求了工具 => 逐个执行，结果回填历史并记录足迹
            for tc in reply.tool_calls:
                observation = self._tools.invoke(tc.name, tc.arguments)
                state.ass_tool_result(tc.id, observation)
                state.steps.append(
                    StepRecord(
                        step_no=state.step_no,
                        thought=reply.content,
                        tool_name=tc.name,
                        tool_args=tc.arguments,
                        observation=observation,
                        status="done"
                    )
                )
            # 6) 进入下一轮
            state.step_no += 1

        # 步数耗尽兜底：不再给工具，强制让模型直接回答
        if not answered:
            logger.warning("agent hit max_steps=%d; forcing final answer", self._max_steps)
            raw = await self._client.chat_complete(state.messages, tools=None)
            final_answer = (parse_assistant_message(raw).content or '(超出最大推理步数,未能给出结论)')

        return final_answer, state.steps
