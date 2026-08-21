"""Agent 消息规划：构建发送给 LLM 的完整消息序列。

本模块负责把"系统提示词 + 历史对话 + 当前用户问题"组装成一份
OpenAI 兼容的 messages 列表，供 agent 循环发送给模型。

- SYSTEM_PROMPT  系统提示词：定义助手行为与工具调用规则
- build_message  组装消息序列（纯函数，无副作用）

核心价值：把"拼 messages"的逻辑集中在一处，其它地方只管传
history 和 user_message，避免各处重复拼装。
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "你是一个具备工具调用能力的助手。规则:\n"
    "- 当需要外部信息(如当前时间)或精确计算时,调用对应工具,再据结果作答。\n"
    "- 若无需工具即可回答,直接给出最终回答,不要调用工具。\n"
    "- 工具返回的 observation 是 JSON 字符串,请基于其中的字段作答。\n"
    "- 每次只调用必要的工具,避免重复调用同一工具获取相同信息。\n"
)


def build_message(history: list[dict], user_message: str) -> list[dict]:
    """构建发送给 LLM 的完整 messages 列表。

    结构固定为三段：
    1. system  系统提示词（在最前，定义角色与规则）
    2. history 历史消息（保持原有顺序，作为上下文）
    3. user    当前用户问题（追加在最后）

    输入：
    - history      历史消息列表（OpenAI 兼容格式），可为空
    - user_message 当前用户提问文本

    输出：OpenAI 兼容的 messages 列表。

    示例：
    空历史：
    >>> build_message([], "今天几号？")[0]["role"]
    'system'
    >>> build_message([], "今天几号？")[-1]
    {'role': 'user', 'content': '今天几号？'}

    带历史：
    >>> msgs = build_message(
    ...     [{"role": "user", "content": "你好"},
    ...      {"role": "assistant", "content": "你好,有什么可以帮你?"}],
    ...     "现在几点?",
    ... )
    >>> [m["role"] for m in msgs]
    ['system', 'user', 'assistant', 'user']
    >>> msgs[-1]["content"]
    '现在几点?'
    >>> msgs[1:3]
    [{'role': 'user', 'content': '你好'}, {'role': 'assistant', 'content': '你好,有什么可以帮你?'}]
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages
