# 08 · 多 Agent 协作

> 05 工作流编排的深度子项。多个角色化 Agent 由 supervisor/router 统一调度：按意图分发、handoff 移交、并行/串行编排、共享上下文，最终合成终答。区别于 07 单 Agent 的 ReAct 循环。

## 现状对齐（基于现有代码）

> 以下路径相对 `apps/ai-service/`。

- **现仅剩一个单轮服务**：companion（`companion_service.py:48` `stream_answer`，`SYSTEM_PROMPT` `:27`）。chat/triage/science 已随重构移除——「四个角色 Agent」的基座不复存在；多 Agent 层需随 03（RAG 重建）先把分诊/科普能力重新落地，再包装为子 Agent。
- **前端硬路由**：现仅 `auth/companion/smart_tts` 三个路由（`app/api/routes/`，`main.py:37-39` 注册）。**无统一入口、无调度者、无 Agent 间消息传递**。
- 可复用基座：SSE（`companion.py:22` `_SSE_HEADERS`、`:43` `companion_chat`，`llm_client.py:86` `_parse_delta`）；会话/消息持久化（`db/models.py` `Conversation` `:32` / `Message` `:43`，`companion_service.py:139` `_persist` 双消息模式）；中断持久化（`companion_service.py:70` `CancelledError`）；鉴权与 RBAC（`deps.py:22` `CurrentUser`、`rbac.py:18` `ROLE_SCOPES` / `:28` `Principal` / `:44` `scopes_for`）。
- 权限隔离：`rbac.py` 保留 role→scope 收敛（`ROLE_SCOPES`、`scopes_for:44`）——多 Agent 调度时子 Agent 权限须沿用此收敛，supervisor 不越权聚合。
- 路由决策信号：原 science 话题漂移检测已移除（需随 03 重建 embedding 相似度），可复用为「路由 Agent」判别意图的依据。
- **无**：Agent 抽象/注册表、supervisor/router、handoff、共享黑板/共享状态、多 Agent trace、防循环调用与全局终止控制。

## 目标

在现有（及随 03/07 重建的）单轮服务之上构建多 Agent 协作层：supervisor/router 统一入口，按意图分发到子 Agent，支持 handoff 移交、并行/串行编排、共享上下文与终止控制，复用 SSE / 持久化 / RBAC。

## 任务

### 1. Agent 抽象与注册
- [ ] `app/services/agent/base.py`：统一 `AgentBase`（name / system_prompt / llm_client / `stream`），收敛 `companion_service` 的 `stream_answer` / `_persist` / `_load_history`（对齐 01 `ConversationContext` 收敛）
- [ ] `app/services/agent/registry.py`：注册子 Agent，懒加载初始化（参考 `companion_service.py:228` 单例模式）
- [ ] 子 Agent 注册：`companion_agent`（现成）+ `triage_agent` / `science_agent` / `chat_agent`（随 03 RAG 重建后包装）

### 2. Supervisor / Router（调度者）
- [ ] `app/services/agent/supervisor.py`：统一入口 `stream_orchestrate`，先路由/规划再分发
- [ ] 路由策略 A（先落地）：规则路由（关键词 + embedding 相似度，随 03 重建话题向量思路）
- [ ] 路由策略 B：LLM 路由（让 LLM 输出目标 Agent 名，纯文本解析以兼容本地小模型，`config.py:37` qwen2.5）
- [ ] handoff：子 Agent 可声明转交（如 triage 判定非医疗问题 -> handoff 到 science/companion），上下文随移交传递

### 3. 共享状态与消息传递
- [ ] `app/services/agent/context.py`：`OrchestrationContext`（全局 messages + 各 Agent 局部 history + 轮次/终止标记），区别于现有线性 history（`companion_service.py:125`）
- [ ] 黑板/消息总线：子 Agent 产出作为 `Observation` 写回共享 context，供下一步路由/合成参考

### 4. 并行与串行编排
- [ ] 并行：多子 Agent 同时检索/推理（如 triage + science 并行取片段），`asyncio.gather`（复用 `companion_service.py:53` `anyio.to_thread` 同步桥接模式）
- [ ] 串行 pipeline：规划 -> 子 Agent -> 合成 -> 终答

### 5. 终止与防循环
- [ ] 全局 max rounds、重复调用检测（同 Agent 连续 handoff 上限）、无进展熔断
- [ ] 终由 supervisor 合成终答并 `_persist`（对齐 `companion_service.py:139` 双消息收尾）

### 6. 流式输出
- [ ] SSE 事件扩展：`route`(目标 Agent) / `agent_delta`(某 Agent 输出) / `handoff` / `final_delta` / `done`，沿用 `companion.py` SSE 与 `_parse_delta`（`llm_client.py:86`）
- [ ] 前端展示多 Agent 推理链（参考 `apps/h5-app2` 逐字渲染 + Agent 标签）

### 7. 路由接入
- [ ] `app/api/routes/agent.py`：`POST /api/agent/stream` 统一入口，复用 `deps.py:22` `CurrentUser` 与 `rbac.py` 角色；在 `main.py` 注册路由（对齐 `main.py:37-39`）
- [ ] 子 Agent 权限收敛：沿用 `rbac.py:44` `scopes_for` 的 role→scope 收敛，supervisor 不越权聚合跨 scope 内容

### 8. 安全与成本
- [ ] 多 Agent 放大 token：总 token 预算 + 单 Agent 预算（依赖 06 trace）
- [ ] 子 Agent 失败兜底，单 Agent 崩溃不影响整链（对齐 04 错误语义）
- [ ] 敏感操作绑定 RBAC role（`rbac.py:18` `ROLE_SCOPES`）

## 示例执行流

```
用户: 我最近头晕，还有点焦虑睡不着
route: triage_agent (主诉头晕)
  triage: 建议神经内科；伴焦虑失眠非急症
handoff: companion_agent (情绪陪伴)
  companion: 失眠焦虑的舒缓建议
supervisor final: 综合分诊 + 陪伴建议（持久化为 assistant 消息）
```

## 依赖

- 强依赖 01（Agent 内核 / `ConversationContext` 收敛）、04（工具 / Skill）；弱依赖 05（与 ReAct / Plan-Execute 并存为另一种工作流形态）、06（多 Agent trace / Token / 耗时）、02（共享上下文剪裁）、03（子 Agent 检索增强）。
