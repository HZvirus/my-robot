"""Agent 端点的 Pydantic DTO（数据传输对象）。

这三个模型负责 API 边界上的**请求/响应数据格式校验与转换**：

- AgentRunRequest    POST /agent/run 的请求体（用户提问 + 会话 ID）
- AgentStepOut       响应中的单步推理足迹（对应 AgentStep 表 / StepRecord）
- AgentRunResponse   响应的整体结构（会话 ID + 最终答案 + 步骤列表）

命名约定：对外 JSON 使用 **camelCase**（沿用 companion 风格），
内部 Python 字段使用 **snake_case**，通过 ``alias`` 映射；
``populate_by_name=True`` 使构造时既可用别名（camelCase）也可用字段名。
"""

from pydantic import BaseModel, ConfigDict, Field


class AgentRunRequest(BaseModel):
    """发起一次 agent 运行的请求体。

    - message          用户提问（必填，去空白后至少 1 个字符）
    - conversation_id  会话 ID；不传则服务端创建新会话（camelCase 为 conversationId）

    输入输出示例：
    >>> AgentRunRequest.model_validate({"message": "现在几点?"})
    AgentRunRequest(message='现在几点?', conversation_id=None)
    >>> AgentRunRequest.model_validate({"message": "现在几点?", "conversationId": "conv-1"})
    AgentRunRequest(message='现在几点?', conversation_id='conv-1')

    受 populate_by_name 影响，也可直接写 snake_case 字段名：
    >>> AgentRunRequest(message="你好", conversation_id="conv-2").conversation_id
    'conv-2'

    message 为空/缺省时校验失败：
    >>> try:
    ...     AgentRunRequest.model_validate({"message": ""})
    ... except Exception as exc:
    ...     type(exc).__name__
    'ValidationError'
    """

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")


class AgentStepOut(BaseModel):
    """响应中的单步推理足迹（一步 ReAct 循环的可读形态）。

    字段与 AgentStep 表 / state.StepRecord 一一对应，供前端渲染
    "AI 推理过程"。输出 JSON 中 step_no 以 stepNo 呈现。

    输入输出示例：
    >>> AgentStepOut(step_no=0, thought="取当前时间",
    ...              action="get_current_time", observation='"20:00"')
    AgentStepOut(step_no=0, thought='取当前时间', action='get_current_time', observation='"20:00"', status='done')

    status 缺省时用默认值 "done"：
    >>> AgentStepOut(step_no=1, thought="x", action="y", observation="z").status
    'done'
    """

    model_config = ConfigDict(populate_by_name=True)

    step_no: int = Field(alias="stepNo")
    thought: str = ""
    action: str = ""
    observation: str = ""
    status: str = "done"


class AgentRunResponse(BaseModel):
    """agent 运行完成的响应体。

    - conversation_id  本次会话 ID（camelCase 为 conversationId）
    - answer           最终答案文本
    - steps            推理足迹列表（可为空数组，说明模型直接回答了）

    输入输出示例：
    >>> resp = AgentRunResponse(
    ...     conversation_id="conv-1",
    ...     answer="现在是 20:00",
    ...     steps=[AgentStepOut(step_no=0, thought="先取时间",
    ...                         action="get_current_time", observation='"20:00"')],
    ... )
    >>> resp.answer
    '现在是 20:00'
    >>> resp.steps[0].step_no
    0

    序列化回 camelCase JSON（给前端）：
    >>> resp.model_dump(by_alias=True)
    {'conversationId': 'conv-1', 'answer': '现在是 20:00', 'steps': [{'stepNo': 0, 'thought': '先取时间', 'action': 'get_current_time', 'observation': '"20:00"', 'status': 'done'}]}

    steps 缺省时为空列表：
    >>> AgentRunResponse(conversation_id="c", answer="直接回答").steps
    []
    """

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    answer: str
    steps: list[AgentStepOut] = []
