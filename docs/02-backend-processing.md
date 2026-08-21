# 02 · 后端处理

## 1. 请求入口：FastAPI 路由

所有路由在 `app/api/routes/` 下，统一挂载到 `/api` 前缀（见 `app/main.py`）。流式接口的写法完全一致：

```python
@router.post("/triage/chat")
async def triage_chat(req: TriageRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in triage_service.stream_answer(req.message, req.conversation_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

要点：

- `StreamingResponse` + `media_type="text/event-stream"`；`X-Accel-Buffering: no` 防止反向代理缓冲。
- `ensure_ascii=False` 保证中文原文输出。
- 客户端断开时 `CancelledError` 直接 `raise`，由服务层负责收尾落库。

非流式 GET 接口（历史/会话列表/科室列表）走普通 `response_model`：

- `GET /api/triage/history/{conversation_id}`
- `GET /api/triage/conversations`
- `GET /api/triage/departments`
- chat / companion 有对应的 `history` 与 `conversations`。

## 2. 服务层处理流程（以导诊为例）

`TriageService.stream_answer()`（`app/services/triage_service.py`）的单轮数据流：

```
取/生成 conversation_id
  → 确保 Conversation 行存在
  → 从 SQLite 取最近 TRIAGE_MAX_HISTORY 条历史
  → yield {conversationId}
  → embed(query) 得到查询向量
  → ChromaDB query(top_k=4)
  → 组装 sources，yield {sources}
  → 拼 system + history + user
  → Ollama 流式生成，逐个 yield {delta}
  → 流结束后：落库 user+assistant → 解析推荐科室 → yield {department, matchedDepartments}
  → yield {done}
```

通用聊天（`ChatService`）与健康陪伴（`CompanionService`）去掉「检索」环节，结构相同。

## 3. 上下文拼接

统一模式：`[system 提示词] + 最近 N 条历史 + [当前用户消息]`。

- 历史限制：`msgs.extend(history[-SETTING_MAX_HISTORY:])`。
- 导诊额外把检索片段以 `[1]`、`[2]`… 编号注入 system 提示词的「【医院资料】」区块（`_format_context`），并做**上下文预算**：累计不超过 `CONTEXT_BUDGET = 4000` 字符，超长片段截断，避免 14B 模型上下文溢出。

## 4. 流式累积与落库

```python
parts: list[str] = []
completed = False
try:
    async for token in self._client.chat_stream(messages):
        parts.append(token)
        yield {"delta": token}
    completed = True
except asyncio.CancelledError:
    self._persist(conv_id, message, "".join(parts), sources, interrupted=True)
    raise                      # 客户端断开：保存部分内容
except Exception as exc:
    yield {"error": f"生成失败: {exc}"}
    self._persist(conv_id, message, "".join(parts), sources, interrupted=True)
    return                     # 服务端异常：输出 error 事件后正常收尾
if completed:
    self._persist(conv_id, message, "".join(parts), sources, interrupted=False)
    yield {"done": True}
```

- `parts` 累积完整回复，流结束（无论成败）才写库，避免每帧落库。
- `asyncio.CancelledError` 是 `BaseException` 子类，`except Exception` 不会吞掉它，两个分支语义清晰。
- 落库使用同步 SQLAlchemy 会话（`_session_scope`），在取消瞬间仍能原子完成，不会被中断。

## 5. 数据库访问

- `app/db/session.py`：`engine`（默认 `sqlite:///./app.db`）、`SessionLocal`、`Base`。
- `app/db/models.py`：`Conversation`、`Message`（`sources` 为 JSON 列，仅导诊使用；`interrupted` 标记中断）。
- 每个服务通过 `sessionmaker[Session]` 依赖注入，测试时可换内存库（`tests/test_triage.py` 用 `sqlite://` + `StaticPool`）。

## 6. 历史与会话列表

- `get_history(conversation_id)`：按 `created_at` 正序返回该会话全部消息（导诊含 sources）。
- `list_conversations()`：按创建时间倒序，取每个会话首条用户消息前 60 字作预览。

## 7. DTO：camelCase 对齐

后端 Pydantic 字段用 snake_case，对外 JSON 用 camelCase 别名，避免与前端 TS 类型不一致：

```python
class TriageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, alias="conversationId")
```

FastAPI 默认 `response_model_by_alias=True`，因此历史/会话列表接口输出的也是 camelCase。

## 8. 测试

`apps/ai-service/tests/`：

- `test_triage.py`：文本分块边界、SSE 事件序列与落库、历史拼接、取消时部分落库（`interrupted`）。
- `test_chat.py`、`test_companion.py`、`test_tts.py`、`test_health.py`：对应模块的冒烟测试。
- 测试用假客户端（fake `OllamaClient`）注入 `TriageService`，无需真实 Ollama。

校验命令：`ruff check .`、`mypy app`、`pytest`。
