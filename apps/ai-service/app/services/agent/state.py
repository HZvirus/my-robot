"""Agent 状态管理：ReAct 循环中消息与步骤的数据结构。

本模块定义 agent 循环中使用的轻量数据类（dataclass），只负责**保存与转换
格式**，不涉及业务逻辑：

- ToolCall        一次函数调用（工具名 + 参数）
- AssistantReply  AI 的一条回复（可含文本和/或工具调用）
- StepRecord      一轮思考-行动-观察的记录（用于审计/展示推理过程）
- AgentState      整个 agent 会话的运行状态（消息历史 + 步骤历史）

核心价值：把 LLM API 返回的字典格式，和存库/转发的字典格式，统一抽象为
强类型对象，避免到处手写字典 key。
"""

from __future__ import annotations

import json

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """一次工具（函数）调用。

    对应 OpenAI 风格 tool_calls 中的一个元素：
    - id          调用唯一标识（后续 tool 结果消息用 tool_call_id 回填它）
    - name        工具名，如 "search_kb"
    - arguments   解析后的参数字典，如 {"query": "感冒吃什么"}

    示例：
    >>> tc = ToolCall(id="call_abc123", name="search_kb",
    ...               arguments={"query": "感冒吃什么"})
    >>> tc.id
    'call_abc123'
    >>> tc.name
    'search_kb'
    >>> tc.arguments
    {'query': '感冒吃什么'}
    """

    id: str
    name: str
    arguments: dict


@dataclass
class AssistantReply:
    """AI 的一次回复。

    一次回复可以是纯文本（content），也可以携带零到多个工具调用
    （tool_calls），两者可同时存在（先给理由，再要求调用工具）。

    示例：
    纯文本回复：
    >>> reply = AssistantReply(content="感冒多喝热水。")
    >>> reply.content
    '感冒多喝热水。'
    >>> reply.tool_calls
    []
    >>> reply.wants_tool
    False

    携带工具调用：
    >>> reply2 = AssistantReply(
    ...     content="我查一下知识库",
    ...     tool_calls=[ToolCall(id="call_1", name="search_kb", arguments={})],
    ... )
    >>> reply2.wants_tool
    True
    """

    content: str = ''
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tool(self) -> bool:
        """是否请求调用工具：只要 tool_calls 非空即为 True。

        供循环判断用：为 True 则执行工具并继续，为 False 则本轮结束、
        把 content 作为最终答案。

        示例：
        >>> AssistantReply().wants_tool
        False
        >>> AssistantReply(tool_calls=[ToolCall("c1", "search_kb", {})]).wants_tool
        True
        """
        return bool(self.tool_calls)


def parse_assistant_message(msg: dict) -> AssistantReply:
    """把 LLM API 返回的 assistant 消息字典，解析成 AssistantReply。

    容错处理：
    - content 缺省时回退为空串
    - tool_calls 缺省时为 []（纯文本回复）
    - arguments 是 JSON 字符串，解析失败时回退为 {}（不中断流程）

    示例：
    纯文本回复：
    >>> parse_assistant_message({"role": "assistant", "content": "你好"})
    AssistantReply(content='你好', tool_calls=[])

    携带工具调用（arguments 是 JSON 字符串，会被解析成 dict）：
    >>> parse_assistant_message({
    ...     "role": "assistant",
    ...     "content": "我来查一下",
    ...     "tool_calls": [
    ...         {"id": "call_9",
    ...          "type": "function",
    ...          "function": {"name": "search_kb",
    ...                       "arguments": '{"query": "感冒"}'}},
    ...     ],
    ... })
    AssistantReply(content='我来查一下', tool_calls=[ToolCall(id='call_9', name='search_kb', arguments={'query': '感冒'})])

    arguments 是非法 JSON 时回退为空 dict：
    >>> parse_assistant_message({
    ...     "tool_calls": [
    ...         {"id": "call_x",
    ...          "function": {"name": "f", "arguments": "not-json"}},
    ...     ],
    ... }).tool_calls[0].arguments
    {}
    """
    content = msg.get('content') or ''
    calls: list[ToolCall] = []
    for raw in msg.get('tool_calls') or []:
        fn = raw.get('function') or {}
        try:
            args = json.loads(fn.get('arguments') or '{}')
        except (ValueError, TypeError):
            args = {}
        calls.append(ToolCall(id=raw.get('id') or '', name=fn.get('name') or '', arguments=args))
    return AssistantReply(content=content, tool_calls=calls)


@dataclass
class StepRecord:
    """一轮 ReAct 循环的足迹记录（对应 agent_steps 表的一行）。

    - thought      本轮 assistant 的文本（推理理由）
    - tool_name    调用的工具名；**最终答案轮没有工具调用，此处为 ""**
    - tool_args    传给工具的参数（字典）
    - observation  工具返回的结果（JSON 字符串），用于审计/回放
    - status       步骤状态（done 等），默认 "done"

    示例：
    >>> rec = StepRecord(step_no=1, thought="先查知识库", tool_name="search_kb",
    ...                  tool_args={"query": "感冒"}, observation="[]")
    >>> rec.step_no
    1
    >>> rec.action_json()
    '{"tool": "search_kb", "args": {"query": "感冒"}}'

    最终答案轮（无工具调用）：
    >>> final = StepRecord(step_no=2, thought="据此作答", tool_name="",
    ...                    tool_args={}, observation="")
    >>> final.action_json()
    '{"tool": "", "args": {}}'
    """

    step_no: int
    thought: str          # 本轮 assistant 文本(理由)
    tool_name: str        # 最终答案轮为 ""
    tool_args: dict
    observation: str      # 工具结果 JSON 字符串
    status: str = "done"

    def action_json(self) -> str:
        """把动作（工具名+参数）序列化为 JSON 字符串，便于存库展示。

        ensure_ascii=False 保证中文等非 ASCII 字符原样输出，可读性好。

        示例：
        >>> StepRecord(1, "查", "search_kb", {"query": "感冒"}, "").action_json()
        '{"tool": "search_kb", "args": {"query": "感冒"}}'
        """
        return json.dumps({"tool": self.tool_name, "args": self.tool_args}, ensure_ascii=False)


@dataclass
class AgentState:
    """一次 agent 会话的完整运行状态。

    - messages  与 LLM 往返的完整消息历史（字典列表，OpenAI 兼容格式），
                每轮循环都会回传给模型作为上下文
    - steps     已完成的 StepRecord 列表，用于落库展示推理过程
    - step_no   当前步骤计数（下一个 step_no 从 1 开始递增）

    示例：
    >>> st = AgentState()
    >>> st.step_no
    0
    >>> st.messages
    []
    """

    messages: list[dict] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)
    step_no: int = 0

    def add_assistant(self, reply: AssistantReply) -> None:
        """把 AssistantReply 转换回 OpenAI 兼容的字典格式，追加进消息历史。

        空 content / 空 tool_calls 的字段不写入，保持消息体精简，
        避免给模型回传无意义字段。

        示例：
        纯文本回复：
        >>> st = AgentState()
        >>> st.add_assistant(AssistantReply(content="你好"))
        >>> st.messages
        [{'role': 'assistant', 'content': '你好'}]

        携带工具调用（arguments 会被序列化回 JSON 字符串）：
        >>> st2 = AgentState()
        >>> st2.add_assistant(AssistantReply(
        ...     content="我查一下",
        ...     tool_calls=[ToolCall(id="call_1", name="search_kb",
        ...                          arguments={"query": "感冒"})],
        ... ))
        >>> st2.messages[0]["tool_calls"]
        [{'id': 'call_1', 'type': 'function', 'function': {'name': 'search_kb', 'arguments': '{"query": "感冒"}'}}]
        """
        msg: dict = {'role': 'assistant'}
        if reply.content:
            msg['content'] = reply.content
        if reply.tool_calls:
            msg['tool_calls'] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                    }
                }
                for tc in reply.tool_calls
            ]
        self.messages.append(msg)

    def ass_tool_result(self, call_id: str, content: str) -> None:
        """追加一条工具结果消息，回填对应的 tool_call_id。

        - call_id  必须与之前 assistant 消息里的 tool_calls[].id 一致，
                   模型靠它把结果对应到那次调用
        - content  工具返回的文本/JSON 字符串

        示例：
        >>> st = AgentState()
        >>> st.ass_tool_result(call_id="call_1", content='[{"title": "感冒指南"}]')
        >>> st.messages
        [{'role': 'tool', 'tool_call_id': 'call_1', 'content': '[{"title": "感冒指南"}]'}]
        """
        self.messages.append({
            "role": 'tool',
            "tool_call_id": call_id,
            "content": content
        })
