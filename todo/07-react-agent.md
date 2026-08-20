# 07 · ReAct Agent 落地

> 05 工作流编排的深度子项。ReAct（Reasoning + Acting）：Thought -> Action -> Observation 循环，让 Agent 边推理边调用工具，多步直至给出最终答案。

## 现状对齐（基于现有代码）

- LLM 调用为纯文本流式：`llm_client.chat_stream`（`app/services/llm_client.py:80`），`extra` 已预留透传位（`:99`）但未发 `tools`。
- SSE 流式路由模式已有：`chat.py:51` + `_SSE_HEADERS`（`:24`），SSE 行解析 `_parse_delta`（`llm_client.py:112`）。
- 单轮服务参考实现：`chat_service.stream_answer` retrieve -> prompt -> stream -> persist（`app/services/chat_service.py:38`），含 `CancelledError` 中断持久化（`:60`）。
- 持久化基座：`Conversation`/`Message`（`app/db/models.py`），`_persist` 写双消息模式（`chat_service.py:129`）。
- 可作为 Action 的能力：知识检索（`vector_store`）、科室匹配（`departments.match_departments`）、text-to-sql（`todo/text-to-sql.md`）。
- **无** Thought/Action/Observation 解析、无循环引擎、无步骤持久化。

## 目标

实现一个可流式输出、可中断恢复、步骤可观测的 ReAct 循环，作为 01 Agent 内核的首个工作流实现。

## 任务

### 1. 两种实现路线（先 B 后 A）
- [ ] 路线 A：原生 Function Calling -- `chat_stream` 透传 `tools`/`tool_choice`（经 `extra`），解析 tool_call delta
- [ ] 路线 B（先落地）：纯文本 ReAct -- 用 prompt 约束输出格式 `Thought:/Action:/Observation:`，自写解析器；兼容本地小模型（Ollama qwen2.5，`config.py:64`）

### 2. 输出解析器
- [ ] `app/services/agent/react_parser.py`：从 LLM 流式/完整输出抽取 `Thought`、`Action`(name+args)、`Final Answer`
- [ ] 容错：格式不合规时回退/重试一次，避免死循环（依赖 06 trace 记录解析失败）

### 3. 工具调度
- [ ] `app/services/agent/react_loop.py`：按 Action name 分发到工具（依赖 04 `ToolBase`），结果作为 `Observation` 回填 messages 的下一轮
- [ ] 工具未注册/参数非法/执行异常 -> 生成错误 Observation 让 Agent 自纠

### 4. 循环引擎
- [ ] 终止条件：`Final Answer` / 达 `REACT_MAX_STEPS`（默认 6）/ 超时 / 连续无进展
- [ ] 每步 token 预算与总预算控制（依赖 06）

### 5. 持久化与中断恢复
- [ ] `app/db/models.py` 增 `AgentStep`（conv_id、step_no、thought、action、observation、status、created_at）
- [ ] 复用 `_persist` 双消息模式收尾（`chat_service.py:129`）；中断时落 checkpoint（对齐 `CancelledError` 处理 `chat_service.py:60`），恢复从最后完成步骤续跑

### 6. 流式输出
- [ ] 新增 SSE 事件类型：`thought` / `action` / `observation` / `delta` / `done`，沿用 `chat.py` SSE 模式与 `_parse_delta`
- [ ] 前端可实时展示推理链（参考 `apps/h5-app2` 逐字渲染）

### 7. 路由接入
- [ ] `app/api/routes/react.py`：`POST /api/react/stream`，复用 `CurrentUser` 鉴权（`deps.py`）与 RBAC（`rbac.py`），在 `main.py` 注册路由

### 8. 安全与稳定性
- [ ] max steps + 超时 + 单步重试/熔断；工具失败兜底不让整链崩溃
- [ ] 敏感操作工具绑定 RBAC role（对齐 `rbac.py` ROLE_SCOPES）

## 示例执行流

```
用户: 我最近头晕，该挂什么科？
Thought: 需先检索症状对应的科室知识
Action: kb_search[头晕 对应科室]
Observation: [检索片段] 神经内科 / 耳鼻喉科 ...
Thought: 用户仅头晕，先推荐神经内科
Final Answer: 建议挂神经内科，若伴耳鸣/听力下降可转耳鼻喉科。
```

## 依赖

- 强依赖 01（Agent 内核/状态）、04（工具与 `ToolBase`）；弱依赖 03（kb_search 工具）、06（trace/Token/工具成功率）；与 05（Plan-and-Execute 并存为另一种工作流）。
