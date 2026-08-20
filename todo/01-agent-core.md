# 01 · Agent 核心架构与推理引擎

> JD 对应：智能体在真实业务场景的核心架构与开发 —— 任务规划（Planning）、多步推理、工具调用（Function Calling）、多轮状态管理，复杂逻辑执行稳定性。

## 现状对齐（基于现有代码）

> 以下路径相对 `apps/ai-service/`（重构后整体迁入 pnpm/turbo monorepo，Python 后端在 `apps/ai-service/app/`）。

- **无真正 Agent**。`chat/triage/science` 服务已随重构移除，当前仅剩 `companion` 一个「单轮聊天」服务：`stream_answer` 做 prompt → stream → persist，一次 LLM 调用即结束（`app/services/companion_service.py:48`）。`app/main.py:37-39` 仅挂载 `auth/companion/smart_tts` 三个 router；残留测试 `tests/test_chat.py`、`tests/test_science.py`、`tests/test_triage.py`、`tests/test_tts.py` 仍 import 已删除模块，pytest collect 报 5 个 error。
- 多轮状态管理已有基础：会话与消息持久化在 `app/db/models.py`（`Conversation`/`Message`，另有设备 `User`），`companion_service` 的 `_ensure_conversation`（`companion_service.py:106`）/ `_load_history`（`companion_service.py:125`）取最近 N 条拼入 messages。但仅线性历史拼接，无状态机、无中间步骤持久化。
- **无 Planning、无多步推理、无 Function Calling**：`llm_client.chat_stream` 仅 `/v1/chat/completions` 文本流式（`app/services/llm_client.py:54`），未发送 `tools` 参数（`extra` 已预留透传位 `llm_client.py:60`，全仓无人使用）。
- 新结构：`app/api/routes/`（auth/companion/smart_tts）、`app/core/`（config/logger/rbac 权限域）、`app/models/`（Pydantic schema）、`app/db/`（`models.py` + `session.py`）。

## 目标

在现有单轮服务之上抽象出 Agent 运行内核，支持「感知 → 规划 → 调用工具 → 观察」循环，多步直到完成，并保证执行稳定性。

## 任务

### 1. Agent 运行内核
- [ ] 新建 `app/services/agent/` 包：`agent.py`（运行循环）、`state.py`（AgentState / 步骤记录）、`planner.py`
- [ ] 实现主循环：observe → plan → act(tool) → observe，支持多步，达上限/完成即止
- [ ] 步骤持久化：扩展 `app/db/models.py` 增加 `AgentStep`（conv_id、step_no、thought、action、observation、status），支撑中断恢复（见 05）
- [ ] 单步重试 / 超时 / 熔断，单步失败不崩溃整条链路

### 2. 规划（Planning）
- [ ] `planner.py`：任务分解，产出可执行步骤列表
- [ ] 支持 Plan-and-Execute 与 ReAct 两种模式并存（ReAct 详见 05）

### 3. 工具调用（Function Calling）
- [ ] 扩展 `llm_client.py`：`chat_stream` 支持 `tools` / `tool_choice` 透传（经 `extra`），增加 tool_call delta 解析
- [ ] `app/services/agent/tools.py`：工具调用分发 + 结果回填（messages 增加 `tool` role）
- [ ] 工具契约与错误语义（依赖 04 工具生态）

### 4. 多轮状态管理收敛
- [ ] 抽象 `ConversationContext`（history + agent state + working memory），收敛 `companion_service` 中 `_ensure_conversation` / `_load_history` / `_persist`（`companion_service.py:106/125/139`），供后续 chat/triage/science 等服务复用
- [ ] 状态快照与恢复（为 05 中断恢复铺垫）

## 依赖

- 强依赖 04（工具生态）、05（工作流）；弱依赖 06（trace 贯穿步骤）。
