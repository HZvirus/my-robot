"""Agent 工具：工具注册与内置工具（时间、计算器、网页搜索）。

本模块实现 agent 可调用的"工具"机制：

- Tool               单个工具的定义（名字 + 描述 + 参数 Schema + 可执行函数）
- get_current_time   内置工具：取当前 UTC 时间
- calculate          内置工具：纯算术表达式求值（用 ast 解析，安全，不用 eval）
- web_search         内置工具：DuckDuckGo 网页搜索（免 Key）
- ToolRegistry       工具注册表：管理工具集合，向 LLM 提供 JSON Schema、
                     按名字分发调用

核心价值：
- LLM 通过 `schema()` 知道有哪些工具、参数长什么样；
- agent 决定调用工具后，通过 `invoke()` 统一分发执行，返回结果字符串。
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib import parse as urlparse

import httpx

from app.core.config import settings


@dataclass
class Tool:
    """一个工具的定义。

    - name         工具名，LLM 调用时用的标识，如 "calculate"
    - description  给 LLM 看的说明，描述何时调用
    - parameters   参数对象的 JSON Schema，LLM 据此生成合法参数
    - func         实际执行函数；调用时以解析后的参数作为 kwargs

    示例：
    >>> t = Tool(name="calculate", description="计算",
    ...          parameters={"type": "object"}, func=calculate)
    >>> t.name
    'calculate'
    """

    name: str
    description: str
    parameters: dict            # arguments 对象的 JSON Schema
    func: Callable[..., str]    # 以解析后的参数为 kwargs 调用


def get_current_time() -> str:
    """获取当前 UTC 时间(ISO 8601)。

    无参数工具，返回 ISO 8601 字符串，如 "2026-08-21T11:24:43.123456+00:00"。

    示例：
    >>> import re
    >>> bool(re.match(r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}", get_current_time()))
    True
    """
    return datetime.now(UTC).isoformat()


def calculate(expression: str) -> str:
    """对纯算术表达式求值(仅 + - * / 与数字)。

    用 `ast` 解析表达式而不是 `eval`，从根本上避免执行任意代码，
    保证安全性。支持的节点：四则运算 BinOp、一元负号 UnaryOp、数字常量。

    输入：数学表达式字符串，如 "(1+2)*3"、"10 / 4"。
    输出：JSON 字符串，成功为 {"result": ...}，失败为 {"error": ...}。

    示例：
    成功：
    >>> calculate("(1+2)*3")
    '{"result": 9}'
    >>> calculate("10 / 4")
    '{"result": 2.5}'

    支持负数与负号：
    >>> calculate("-5 + 2")
    '{"result": -3}'

    表达式非法（语法错误）：
    >>> json.loads(calculate("1+"))["error"].startswith("invalid expression")
    True

    含不允许的调用（安全拦截，不执行）：
    >>> json.loads(calculate("__import__('os')"))["error"]
    'unsupported node'
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return json.dumps({"error": f"invalid expression: {exc}"}, ensure_ascii=False)

    def _eval(node: ast.AST) -> float:
        # 递归求值：只接受 Expression / 四则 BinOp / 一元负号 / 数字常量，
        # 其它任何节点（函数调用、属性访问、幂运算等）一律抛 ValueError 拒绝
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            l, r = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                return l + r
            if isinstance(node.op, ast.Sub):
                return l - r
            if isinstance(node.op, ast.Mult):
                return l * r
            return l / r
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("unsupported node")

    try:
        return json.dumps({"result": _eval(tree)})
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


class _DDGHTMLParser(HTMLParser):
    """DuckDuckGo HTML 结果页解析器：提取 标题/真实URL/摘要。

    只关注 `<a class="result__a">`（标题链接）与 `<a class="result__snippet">`
    （摘要链接）两种节点，两者配对出现即构成一条结果。
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._mode: str | None = None   # "title" | "snippet" | None
        self._title: str | None = None
        self._snippet: str | None = None
        self._href: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr = dict(attrs)
        classes = (attr.get("class") or "").split()
        if "result__a" in classes:
            self._mode, self._title, self._href = "title", "", attr.get("href") or ""
        elif "result__snippet" in classes:
            self._mode, self._snippet = "snippet", ""

    def handle_data(self, data: str) -> None:
        if self._mode == "title" and self._title is not None:
            self._title += data
        elif self._mode == "snippet" and self._snippet is not None:
            self._snippet += data

    def handle_endtag(self, tag: str) -> None:
        if tag != "a":
            return
        if self._mode == "title" and self._title is not None:
            self._title = " ".join(self._title.split())
            self._mode = None
        elif self._mode == "snippet" and self._snippet is not None:
            self._snippet = " ".join(self._snippet.split())
            self._mode = None
            self.results.append({
                "title": self._title or "",
                "url": _real_url(self._href),
                "snippet": self._snippet or "",
            })
            self._title = self._snippet = None
            self._href = ""


def _real_url(href: str) -> str:
    """把 DuckDuckGo 的 `/l/?uddg=...` 跳转链接还原为真实 URL。

    示例：
    >>> _real_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage%3Fa%3D1")
    'https://example.com/page?a=1'
    >>> _real_url("https://example.com/plain")
    'https://example.com/plain'
    """
    if "uddg=" not in href:
        return href
    qs = urlparse.urlsplit(href).query
    return urlparse.parse_qs(qs).get("uddg", [href])[0]


_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://duckduckgo.com/",
}


def web_search(query: str, max_results: int = settings.WEB_SEARCH_MAX_RESULTS) -> str:
    """DuckDuckGo 网页搜索（免 Key），返回 JSON 格式的结果列表。

    - query       搜索关键词
    - max_results 最多返回多少条结果

    输出 JSON 结构：{"query": ..., "results": [{"title", "url", "snippet"}, ...]}
    - 无结果时 results 为空数组
    - 网络/解析失败时返回 {"error": ...}
    - 自动过滤广告条目（DDG 广告链接带 ad_domain/ad_provider 参数）

    注意：
    - 这是一个网络方法，需要外网可达，无法离线 doctest；
      解析器与 URL 还原是纯函数，可离线测试（见 _DDGHTMLParser / _real_url）。
    - html 端点对裸 User-Agent 有反爬（返回 202 挑战页），必须携带完整浏览器头。
    """
    try:
        with httpx.Client(
            timeout=settings.WEB_SEARCH_TIMEOUT, follow_redirects=True
        ) as client:
            resp = client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=_SEARCH_HEADERS,
            )
            resp.raise_for_status()
    except Exception as exc:  # 网络不可达 / 超时 / HTTP 错误 / 反爬挑战
        return json.dumps({"error": f"search failed: {exc}"}, ensure_ascii=False)

    parser = _DDGHTMLParser()
    parser.feed(resp.text)
    results = [
        r for r in parser.results
        if "ad_domain=" not in r["url"] and "ad_provider=" not in r["url"]
    ]
    return json.dumps(
        {"query": query, "results": results[:max_results]},
        ensure_ascii=False,
    )


_BUILTIN_TOOLS: list[Tool] = [
    Tool(
        name="get_current_time",
        description="获取当前 UTC 时间(ISO 8601)。当用户询问现在几点/日期时调用。",
        parameters={"type": "object", "properties": {}, "required": []},
        func=get_current_time
    ),
    Tool(
        name="calculate",
        description="对纯算术表达式求值(仅支持 + - * / 与数字)。当用户要做数学计算时调用。",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "算术表达式,例如 (1+2)*3"}
            },
            "required": ["expression"],
        },
        func=calculate,
    ),
    Tool(
        name="web_search",
        description=(
            "通过 DuckDuckGo 搜索网页。当用户需要实时/最新资讯或知识库之外的外部资料时调用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词,例如 '2026 年诺贝尔生理学奖 获奖者'",
                },
                "max_results": {"type": "integer", "description": "最多返回多少条结果(默认 5)"}
            },
            "required": ["query"],
        },
        func=web_search,
    ),
]


class ToolRegistry:
    """工具注册表：按名字管理一组工具，并提供调用入口。

    默认实例 `default_registry` 持有 `_BUILTIN_TOOLS`（时间、计算器）。
    """

    def __init__(self, tools: list[Tool] | None = None) -> None:
        """初始化注册表；未传入 tools 时使用内置工具集。

        以 name 为 key 建字典，同名的后注册工具会覆盖前面的。
        """
        self._tools = {t.name: t for t in (tools or _BUILTIN_TOOLS)}

    def schema(self) -> list[dict]:
        """返回 OpenAI 兼容的 tools 参数（喂给 LLM，告知可用工具）。

        示例：
        >>> [s["function"]["name"] for s in ToolRegistry().schema()]
        ['get_current_time', 'calculate', 'web_search']
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in self._tools.values()
        ]

    def name(self) -> list[str]:
        """返回已注册的所有工具名列表。

        示例：
        >>> ToolRegistry().name()
        ['get_current_time', 'calculate', 'web_search']
        """
        return list(self._tools)

    def invoke(self, name: str, arguments: dict) -> str:
        """按名字调用工具，返回结果的 JSON 字符串。

        - name        工具名；未注册时返回 {"error": ...}
        - arguments   工具参数字典，会作为 kwargs 传给工具函数
        - 参数不匹配（TypeError）或工具内部异常都会被捕获，返回错误 JSON，
          而不是让 agent 循环崩溃

        示例：
        调用内置计算器：
        >>> default_registry.invoke("calculate", {"expression": "2*3"})
        '{"result": 6}'

        调用未知工具：
        >>> json.loads(default_registry.invoke("no_such_tool", {}))["error"]
        'unknown tool: no_such_tool'

        参数缺失（TypeError 被捕获）：
        >>> "invalid arguments" in default_registry.invoke("calculate", {})
        True
        """
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        try:
            return tool.func(**arguments)
        except TypeError as exc:
            return json.dumps({"error": f"invalid arguments: {exc}"}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"tool error: {exc}"}, ensure_ascii=False)


# 全局共享的默认注册表，供 agent 循环直接使用
default_registry = ToolRegistry()
