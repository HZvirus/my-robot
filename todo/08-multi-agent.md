# 08 · 多 Agent 协作

> 05 工作流编排的深度子项。多个角色化 Agent 由 supervisor/router 统一调度：按意图分发、handoff 移交、并行/串行编排、共享上下文，最终合成终答。区别于 07 单 Agent 的 ReAct 循环。

## 现状对齐（基于现有代码）

- 现有四个单轮服务即四个天然角色 Agent：分诊 triage（`triage_service.py:53` `TriageService`，SYSTEM_PROMPT `:38`）、科普 science（`science_service.py:48`，"小科" `:28`）、陪伴 companion（`companion_service.py:39`，"小安" `:27`）、通用 chat（`chat_service.py:29`，SYSTEM_PROMPT `:23`）。各自 `stream_answer` 一次 LLM 调用即结束（`chat_service.py:38`、`triage_service.py:66`）。
- **前端硬路由**到各 service：各自独立路由（`chat.py`/`triage.py`/`science.py`/`companion.py`），在 `main.py:68` 注册。**无统一入口、无调度者、无 Agent 间消息传递**。
- 可复用基座：SSE（`chat.py:24` `_SSE_HEADERS`、`:51` `chat_stream`，`llm_client.py:112` `_parse_delta`）；会话/消息持久化（`models.py` `Conversation` `:32` / `Message` `:43`，`chat_service.py:129` `_persist` 双消息模式）；中断持久化（`chat_service.py:60` `CancelledError`）；鉴权与 RBAC（`deps.py:22` `CurrentUser`、`rbac.py:18` `ROLE_SCOPES` / `:28` `Principal` / `:44` `scopes_for`）。
- 权限隔离先例：triage 已按 role 收敛 KB scope 并做 defense-in-depth 过滤（`triage_service.py:84` `scopes_for`、`:102` `allowed` 过滤）——多 Agent 调度时子 Agent 权限须沿用此收敛，supervisor 不越权聚合。
- 路由决策信号先例：science 话题漂移检测（`science_service.py:138` `_is_new_topic`，embedding 相似度 `_cosine_similarity` `:39`），可复用为「路由 Agent」判别意图的依据。
- **无**：Agent 抽象/注册表、supervisor/router、handoff、共享黑板/共享状态、多 Agent trace、防循环调用与全局终止控制。

## 目标

在现有四服务之上构建多 Agent 协作层：supervisor/router 统一入口，按意图分发到子 Agent，支持 handoff 移交、并行/串行编排、共享上下文与终止控制，复用 SSE / 持久化 / RBAC。

## 任务

### 1. Agent 抽象与注册
- [ ] `app/services/agent/base.py`：统一 `AgentBase`（name / system_prompt / llm_client / `stream`），收敛四 service 重复的 `stream_answer` / `_persist` / `_load_history`（对齐 01 `ConversationContext` 收敛）
- [ ] `app/services/agent/registry.py`：注册子 Agent，懒加载初始化（参考 `vector_store.py` `get_vector_store` 单例模式）
- [ ] 现有四 service 包装为 Agent：`triage_agent` / `science_agent` / `companion_agent` / `chat_agent`

### 2. Supervisor / Router（调度者）
- [ ] `app/services/agent/supervisor.py`：统一入口 `stream_orchestrate`，先路由/规划再分发
- [ ] 路由策略 A（先落地）：规则路由（关键词 + embedding 相似度，复用 `science_service.py:138` 话题向量思路）
- [ ] 路由策略 B：LLM 路由（让 LLM 输出目标 Agent 名，纯文本解析以兼容本地小模型，`config.py:64` qwen2.5）
- [ ] handoff：子 Agent 可声明转交（如 triage 判定非医疗问题 -> handoff 到 science/companion），上下文随移交传递

### 3. 共享状态与消息传递
- [ ] `app/services/agent/context.py`：`OrchestrationContext`（全局 messages + 各 Agent 局部 history + 轮次/终止标记），区别于现有线性 history（`chat_service.py:115`）
- [ ] 黑板/消息总线：子 Agent 产出作为 `Observation` 写回共享 context，供下一步路由/合成参考

### 4. 并行与串行编排
- [ ] 并行：多子 Agent 同时检索/推理（如 triage + science 并行取片段），`asyncio.gather`（复用 `anyio.to_thread` 同步桥接模式 `triage_service.py:74`）
- [ ] 串行 pipeline：规划 -> 子 Agent -> 合成 -> 终答

### 5. 终止与防循环
- [ ] 全局 max rounds、重复调用检测（同 Agent 连续 handoff 上限）、无进展熔断
- [ ] 终由 supervisor 合成终答并 `_persist`（对齐 `chat_service.py:129` 双消息收尾）

### 6. 流式输出
- [ ] SSE 事件扩展：`route`(目标 Agent) / `agent_delta`(某 Agent 输出) / `handoff` / `final_delta` / `done`，沿用 `chat.py` SSE 与 `_parse_delta`
- [ ] 前端展示多 Agent 推理链（参考 `apps/h5-app1` 逐字渲染 + Agent 标签）

### 7. 路由接入
- [ ] `app/api/routes/agent.py`：`POST /api/agent/stream` 统一入口，复用 `deps.py:22` `CurrentUser` 与 `rbac.py` 角色；在 `main.py:68` 注册路由
- [ ] 子 Agent 权限收敛：沿用 triage scope 隔离（`triage_service.py:84`），supervisor 不越权聚合跨 scope 内容

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
