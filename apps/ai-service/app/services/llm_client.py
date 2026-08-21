"""OpenAI 兼容的异步 LLM 客户端（chat completions）。

单个客户端类即可对接任意 OpenAI 兼容后端，仅靠配置切换、业务代码零改动：

* 本地 Ollama    -> http://localhost:11434        （LLM_ 未设置时回退到 OLLAMA_*）
* 自建 vLLM      -> http://<host>:<port>/v1        （LLM_BASE_URL=...）
* 云端 API(通义) -> https://dashscope.../v1        （LLM_BASE_URL=... + key）

模块级单例 ``llm_client`` 是 services 层唯一使用的实例。

对外提供两个方法：
- ``chat_stream``    流式对话：逐 token 产出内容增量
- ``chat_complete``  一次性对话：完整返回 assistant 消息（可携带工具调用）
"""

from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Ollama 不校验 Bearer 认证；当没有配置 API key 时发送这个占位值，
# 保证请求头格式统一（Authorization 不能为空）。
_DUMMY_AUTH = "Bearer ollama"


class OpenAICompatClient:
    """OpenAI 兼容 ``/v1/chat/completions`` 的异步封装。

    ``base_url`` 可带可不带 ``/v1`` 后缀，调用时会自动补全。
    当 ``api_key`` 为空时发送占位 Bearer（Ollama 会忽略它）。

    示例（_endpoint / _auth 为纯函数，可单独测试）：
    >>> c = OpenAICompatClient(base_url="http://localhost:11434",
    ...                        api_key="", llm_model="qwen3:14b", timeout=120.0)
    >>> c._endpoint("/chat/completions")
    'http://localhost:11434/v1/chat/completions'
    >>> c._auth()
    'Bearer ollama'

    带 /v1 后缀与 api_key 时：
    >>> c2 = OpenAICompatClient(base_url="https://api.example.com/v1",
    ...                         api_key="sk-abc", llm_model="qwen", timeout=30)
    >>> c2._endpoint("/chat/completions")
    'https://api.example.com/v1/chat/completions'
    >>> c2._auth()
    'Bearer sk-abc'
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        llm_model: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.llm_model = llm_model
        self.timeout = timeout

    def _endpoint(self, path: str) -> str:
        """拼接完整的 API 端点 URL；base_url 缺 /v1 时自动补上。

        示例：
        >>> OpenAICompatClient("http://h:11434", "", "m", 1)._endpoint("/chat/completions")
        'http://h:11434/v1/chat/completions'
        """
        base = self.base_url
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}{path}"

    def _auth(self) -> str:
        """构造 Authorization 请求头；无 api_key 时用占位 Bearer。

        示例：
        >>> OpenAICompatClient("u", "", "m", 1)._auth()
        'Bearer ollama'
        >>> OpenAICompatClient("u", "sk-1", "m", 1)._auth()
        'Bearer sk-1'
        """
        return f"Bearer {self.api_key}" if self.api_key else _DUMMY_AUTH

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict[str, object] | None = None,
    ) -> AsyncIterator[str]:
        """流式对话：发起 SSE 流式请求，逐条 yield 内容增量。

        输入：
        - messages     OpenAI 兼容消息列表，如 [{"role":"user","content":"你好"}]
        - temperature  采样温度（可选），如 0.7
        - max_tokens   最大生成 token 数（可选）
        - extra        额外透传给后端的参数（可选），如 {"stop": [...]}

        输出：AsyncIterator[str]，每个元素是内容增量片段（token 级），
        如："你" -> "好" -> "。" 依次 yield。最终由调用方拼接成完整回复。
        流终止（SSE 的 data: [DONE]）不会额外 yield 任何内容。

        注意：这是一个网络方法，需要真实后端配合，无法离线 doctest。
        """
        headers = {"Authorization": self._auth(), "Content-Type": "application/json"}
        payload: dict[str, object] = {
            "model": self.llm_model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra:
            payload.update(extra)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", self._endpoint("/chat/completions"), headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    token = _parse_delta(line)
                    if token is not None:
                        yield token

    async def chat_complete(
            self,
            messages: list[dict],
            *,
            tools: list[dict] | None = None,
            tool_choice: str | dict | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
    ) -> dict:
        """一次性对话：完整返回 assistant 消息（非流式）。

        输入：
        - messages     消息列表，如 [{"role":"user","content":"现在几点?"}]
        - tools        可用工具列表（ToolRegistry.schema() 的输出），可选
        - tool_choice  工具选择策略，如 "auto" 或 {"type":"function",...}，可选
        - temperature  采样温度（可选）
        - max_tokens   最大生成 token 数（可选）

        输出（成功）：choices[0].message 字典，形如：
        - 纯文本回复:   {"role":"assistant", "content":"现在是 20:00"}
        - 请求调工具:   {"role":"assistant", "content":null,
                         "tool_calls":[{"id":"call_1","type":"function",
                                        "function":{"name":"get_current_time",
                                                    "arguments":"{}"}}]}

        输出（无 choices / 异常兜底）：{"role":"assistant", "content":""}

        示例（针对"无 choices 时的兜底逻辑"——通过 mock 后端验证，真实
        网络请求需实际服务，此处仅演示数据结构）：
        >>> # 后端返回空 choices 时返回空 assistant 消息
        >>> # (依赖 httpx 的响应，无法离线执行，仅供阅读)
        ...
        """
        payload: dict[str, object] = {
            "model": self.llm_model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {"Authorization": self._auth(), "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self._endpoint("/chat/completions"), headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return {"role": "assistant", "content": ""}
        return choices[0].get("message") or {"role": "assistant", "content": ""}


def _parse_delta(line: str) -> str | None:
    """解析一行 SSE 数据，返回其中的内容增量；需要跳过的行返回 None。

    SSE 格式：``data: {json}``，最后以 ``data: [DONE]`` 表示流结束。
    逐行处理规则：
    - 空行 / 非 "data:" 开头 / "[DONE]"        -> None（跳过）
    - "data:" 后的 JSON 解析失败               -> None（跳过并记日志）
    - 无 choices 或 delta.content 为空/非字符串 -> None（跳过）
    - 否则返回 delta.content 字符串

    输入输出示例：
    >>> _parse_delta('data: {"choices":[{"delta":{"content":"你好"}}]}')
    '你好'
    >>> _parse_delta('data: [DONE]')
    >>> _parse_delta('')
    >>> _parse_delta('event: ping')
    >>> _parse_delta('data: not-json')
    >>> _parse_delta('data: {"choices":[{"delta":{"role":"assistant"}}]}')

    delta.content 为空 / 非字符串时返回 None：
    >>> _parse_delta('data: {"choices":[{"delta":{"content":""}}]}')
    """
    if not line:
        return None
    line = line.strip()
    if not line.startswith("data:"):
        return None
    payload = line[len("data:"):].strip()
    if payload == "[DONE]":
        return None
    try:
        import json

        obj = json.loads(payload)
    except ValueError:
        logger.debug("unparseable SSE line: %s", payload)
        return None
    choices = obj.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return None
    return content


# 全局共享的默认客户端：优先用 LLM_* 配置，缺失时回退到 Ollama 配置
llm_client = OpenAICompatClient(
    base_url=settings.LLM_BASE_URL or settings.OLLAMA_BASE_URL,
    api_key=settings.LLM_API_KEY or "",
    llm_model=settings.LLM_MODEL or settings.OLLAMA_LLM_MODEL,
    timeout=settings.LLM_TIMEOUT if settings.LLM_TIMEOUT > 0 else settings.OLLAMA_TIMEOUT,
)

__all__ = ["OpenAICompatClient", "llm_client"]
