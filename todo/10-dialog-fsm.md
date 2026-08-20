# 10 · 对话状态机（FSM）

> 01 Agent 内核「多轮状态管理」的深度子项。将多步业务流建模为有限状态机：状态（阶段）+ 转移（出口条件/工具）+ 守卫（不可跳步），强流程业务由 FSM 主导，Agent 循环只在阶段内推理。首个落地为 `docs/09-robot-dialog-flow.md` 的导诊全流程。

## 现状对齐（基于现有代码）

> 以下路径相对 `apps/ai-service/`。

- 现仅 companion 为单轮范式，**无状态机**：`stream_answer` 一次 LLM 调用即结束（`companion_service.py:48`）；chat/triage/science 已随重构移除。
- 多轮状态仅有线性历史：`Conversation`/`Message`（`db/models.py:32/43`），`_load_history` 取最近 N 条拼入 messages（`companion_service.py:125`），无阶段、无状态转移、无中间步骤（`todo/01-agent-core.md` 明确「无状态机」）。
- 中断只标记不恢复：`CancelledError` 持久化 `interrupted=True`（`companion_service.py:70`），无状态快照可续跑。
- 迁移范式：原 `main.py:_run_lightweight_migrations`（`ALTER TABLE` 补建表/列）已随重构移除；现 `main.py:16-20` lifespan 仅 `Base.metadata.create_all`，新增状态表沿用此机制或引入轻量迁移。
- 可复用基座：SSE（`companion.py:22` `_SSE_HEADERS`、`:43` `companion_chat`，`llm_client.py:86` `_parse_delta`）、RBAC（`rbac.py:18` `ROLE_SCOPES`、`deps.py:22` `CurrentUser`）、config（`config.py`）、懒加载单例（参考 `companion_service.py:228`）。
- 已有设计但未落地：`docs/09-robot-dialog-flow.md` 设计了 `DialogStateMachine`（状态图 `:57`、`STATE_CONFIG` 表 `:74`、出口工具触发转移 `:85`、回退路径 `:86`）、`RobotSession`（`current_state` + `working_memory`，`:254`）、`AgentStep`（`:263`）--为本 todo 的首个落地实例。
- 信号先例：原 science 话题漂移检测（`science_service.py:138`）已移除，可随 03 重建后作为自动状态转移的触发信号。

## 目标

抽象可复用的对话状态机引擎：状态定义 + 转移规则 + 守卫 + 快照恢复，强流程业务由 FSM 主导，Agent/工具只在阶段内运行；首个落地承载 `docs/09` 导诊全流程，复用现有持久化 / SSE / RBAC。

## 任务

### 1. FSM 引擎抽象
- [ ] `app/services/agent/fsm.py`：`State`（name / system_prompt / 工具白名单 / 出口）、`Transition`（from -> to / 触发条件 / 守卫）、`StateMachine`（current / transit / can_transit）
- [ ] `STATE_CONFIG` 声明式定义（对齐 `docs/09-robot-dialog-flow.md:74` 表结构）
- [ ] 守卫：仅出口工具可触发转移，防 LLM 跨阶段跳步（`docs/09-robot-dialog-flow.md:85` 设计要点）

### 2. 状态持久化与恢复
- [ ] `app/db/models.py` 增状态表：`SessionState`（session_id / current_state / working_memory / updated_at），对齐 `docs/09-robot-dialog-flow.md:254` `RobotSession`
- [ ] 复用/扩展 `AgentStep` 记录状态转移步骤（thought / action / observation / status，`docs/09-robot-dialog-flow.md:263`）
- [ ] 中断恢复：读回 `current_state` 续跑（修复现有只标记不恢复 `companion_service.py:70`），迁移沿用 `Base.metadata.create_all`（`main.py:19`）或引入轻量迁移

### 3. 跨阶段记忆（working_memory）
- [ ] 阶段产出写入 `working_memory`，供后续阶段引用（`docs/09-robot-dialog-flow.md:276`：主诉摘要 / 已选科室 / 挂号单号）
- [ ] 与 01 `ConversationContext` 收敛对齐，区别于线性 history（`companion_service.py:125`）

### 4. 状态机与 Agent 循环分层
- [ ] FSM 决定当前阶段系统提示词与工具白名单；Agent 循环只在阶段内 ReAct（`docs/09-robot-dialog-flow.md:87` 设计要点）
- [ ] 服务端二次校验工具白名单（`docs/09-robot-dialog-flow.md:239` `_dispatch` 思路），医疗场景安全底线

### 5. 流式输出
- [ ] SSE 事件：`state`(状态转移) / `tool`(工具调用透明) / `delta` / `done`，沿用 `companion.py` SSE 与 `_parse_delta`（`llm_client.py:86`）
- [ ] 前端渲染当前阶段进度（`docs/09-robot-dialog-flow.md:323`）

### 6. 路由接入
- [ ] `app/api/routes/robot.py`（首个落地，`docs/09-robot-dialog-flow.md:300`）：`POST /api/robot/chat` SSE + `GET /state`
- [ ] 复用 `deps.py:22` `CurrentUser` 与 `rbac.py` 角色；在 `main.py` 注册路由（对齐 `main.py:37-39`）

### 7. 配置
- [ ] `app/core/config.py` 增 FSM 相关项（max_steps / step_timeout / max_history / emit_tool_events），对齐 `docs/09-robot-dialog-flow.md:282` 与 `config.py:19-20` 现有风格

## 示例执行流

```
GREETING -> CONSULTING(收集主诉) -> TRIAGE(determine_department)
        -> REGISTER(挂号) -> GUIDING(引导) -> RETURNING(返航) -> GREETING
出口工具 finish_consulting / confirm_department / create_registration
        / finish_guiding / finish_session 触发转移
回退：TRIAGE->CONSULTING(改口)、REGISTER->TRIAGE(挂号失败)
```

## 依赖

- 强依赖 01（Agent 内核 / 多轮状态管理收敛）、04（工具白名单 / `ToolBase`）；弱依赖 05（中断恢复）、06（状态转移 trace / 可观测）、07（阶段内 ReAct 循环）、`docs/09-robot-dialog-flow.md`（首个落地实例）。
