# 05 · 复杂工作流编排与工程性能优化

> JD 对应：ReAct / Plan-and-Execute / 多 Agent 协作；流式输出（SSE）、中断恢复、上下文剪裁；推理效率与 Token 成本；高并发可用性与稳定性。

## 现状对齐（基于现有代码）

- **SSE 流式已有**：`companion.py:22` `_SSE_HEADERS` + `:43` `companion_chat`（`StreamingResponse`）、`:54` 事件帧（`data: {json}\n\n`）。SSE 解析 `_parse_delta`（`llm_client.py:86`）。
- **中断**：`CancelledError` 时持久化 `interrupted=True`（`companion_service.py:70`），但**只标记不恢复**，无法续写半截答案。
- **上下文剪裁**：仅截断（`companion_service.py:125` 取最近 N），无智能剪裁。
- **无** ReAct/Plan-Execute/多 Agent、无 Token 成本管理；并发用 `httpx.AsyncClient`（每次新建 client，`llm_client.py:75`，可优化为复用）。

## 目标

在单轮流式之上构建多步工作流引擎，补齐中断恢复与上下文剪裁，优化 Token 成本与高并发可用性。

## 任务

### 1. 工作流引擎
- [ ] `app/services/agent/workflow.py`：ReAct 循环（thought / action / observation）
- [ ] Plan-and-Execute 模式（规划 → 执行 → 重规划）
- [ ] 多 Agent 协作：角色分工（分诊 Agent / 查询 Agent），消息传递

### 2. 中断恢复
- [ ] 步骤级 checkpoint（依赖 01 `AgentStep` 持久化），恢复时从最后完成步骤续跑
- [ ] 流式中断后前端可「继续」

### 3. 上下文剪裁
- [ ] 智能剪裁（依赖 02 压缩）：token 预算下保留高相关消息

### 4. Token 成本与效率
- [ ] Token 计数与预算（依赖 06 trace）；prompt 压缩、缓存复用（对 LLM 请求/检索结果做缓存）
- [ ] 并发优化：`httpx` client 单例复用、异步检索并行化

### 5. 高并发可用性
- [ ] 限流 / 队列、超时分级、熔断；压测验证

## 依赖

- 依赖 01（Agent 内核/步骤）、02（上下文剪裁）、03（检索并行）、04（工具）、06（Token/耗时指标）。
