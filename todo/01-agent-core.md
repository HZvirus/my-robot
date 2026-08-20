# 01 · Agent 核心架构与推理引擎

> JD 对应：智能体在真实业务场景的核心架构与开发 —— 任务规划（Planning）、多步推理、工具调用（Function Calling）、多轮状态管理，复杂逻辑执行稳定性。

## 现状对齐（基于现有代码）

- 当前**无真正 Agent**。`chat/companion/science/triage` 四服务均为「单轮 RAG/聊天」：`stream_answer` 做 retrieve → prompt → stream → persist，一次 LLM 调用即结束（`app/services/triage_service.py:66`、`app/services/chat_service.py:38`）。
- 多轮状态管理已有基础：会话与消息持久化在 `app/db/models.py`（`Conversation`/`Message`），各服务 `_load_history` 取最近 N 条拼入 messages（`chat_service.py:115`、`triage_service.py:261`）。但仅线性历史拼接，无状态机、无中间步骤持久化。
- **无 Planning、无多步推理、无 Function Calling**：`llm_client.chat_stream` 仅 `/v1/chat/completions` 文本流式（`app/services/llm_client.py:80`），未发送 `tools` 参数（`extra` 已预留透传位 `llm_client.py:99`，但无人使用）。

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
- [ ] 抽象 `ConversationContext`（history + agent state + working memory），收玫 chat/triage/science/companion 四处重复的 `_ensure_conversation` / `_load_history` / `_persist`
- [ ] 状态快照与恢复（为 05 中断恢复铺垫）

## 依赖

- 强依赖 04（工具生态）、05（工作流）；弱依赖 06（trace 贯穿步骤）。
