# 11 · ReAct Agent 现有实现代码走查修复

> 对已落地的 `apps/ai-service/app/services/agent/` 包（ReAct 循环 + 工具 + 持久化）做代码走查，发现的待修复问题清单。均为小步重构/补丁，不影响现有接口。

## 现状对齐（基于现有代码）

- ReAct 主循环：`AgentRunner.run`（`app/services/agent/agent.py:73`），max_steps 兜底（`:124`），解析容错 `parse_assistant_message`（`app/services/agent/state.py:92`）。
- 工具注册表：`ToolRegistry`（`app/services/agent/tools.py:141`），内置时间/计算器工具（`:119`）。
- 持久化：`ConversationContext`（`app/services/agent/context.py:29`），`ensure`（`:90`）、`load_history`（`:119`）、`list_steps`（`:195`）。
- 编排入口：`AgentService.run`（`app/services/agent_service.py:118`），API 层 `app/api/routes/agent.py:13`。

## 任务

### 1. 上下文与持久化（context.py）
- [ ] `load_history` 未过滤 `interrupted` 消息（`context.py:132-142`）：流式输出被取消留下的半成品回复会作为上下文喂给模型，需加 `.where(Message.interrupted == False)`
- [ ] `ensure` 先查后插非原子（`context.py:90-106`）：并发同 `conv_id` 会双双命中 None 导致主键冲突，需 `INSERT ... ON CONFLICT` 或捕获 `IntegrityError` 后重查
- [ ] `list_steps` 返回脱管 ORM 对象（`context.py:195-209`）：`db.close()` 后 detached，当前仅普通列可读，一旦模型加关系字段即 `DetachedInstanceError`，应在会话内转 DTO

### 2. 主循环健壮性（agent.py / state.py）
- [ ] `AgentRunner.run` 无异常兜底（`agent.py:90-127`）：`chat_complete` 网络错误/后端宕机会直接抛，API 层只捕获 `PermissionError` → 用户 500，需 catch 一次并走降级文案分支
- [ ] 空 `tool_call.id` 生成非法 tool 消息（`state.py:135` + `agent.py:108-109`）：`tool_call_id: ""` 回传部分后端会报错，应回退生成 `call_<uuid>`
- [ ] `step_no` 从 0 开始，与 `AgentStep` 表注释「从 1 开始」（`app/db/models.py:120`）语义不一致，需统一

### 3. 工具层（tools.py）
- [ ] `calculate` 中 `bool` 是 `int` 子类（`tools.py:109`）：`calculate("True")` 返回 `{"result": 1}`，应在 `ast.Constant` 分支显式排除 `bool`
- [ ] `calculate` 成功分支未统一 `ensure_ascii=False`（`tools.py:114`）：结果必为数字故无实际影响，仅风格不一致
- [ ] `ToolRegistry` 缺 `register` / `unregister`（`tools.py:141-211`）：工具集只能在构造时注入，`_tools` 为私有，无法按会话/角色动态增删

### 4. 注入通道与导出（agent_service.py / __init__.py）
- [ ] `AgentService.__init__` 创建 `AgentRunner(client=client)`（`app/services/agent_service.py:116`）无法传自定义 `tools` / `max_steps`
- [ ] `app/services/agent/__init__.py` 仅导出 `AgentRunner`/`ToolRegistry`/`default_registry`，未导出 `ConversationContext` / `AgentState` / `StepRecord`

### 5. 测试
- [ ] 补 `tests/test_agent.py` 集成测试（ReAct 循环 + 持久化链路）：参考 `agent_service.py` docstring 的内存 SQLite + 假 LLM 客户端模式（`agent_service.py:37-101`）；现有 `tests/` 仅有 health/companion/auth，agent 零覆盖

## 依赖

- 均为对现有代码的小步修复，无新增模块；修复前建议先补测试（第 5 节）作回归基线。
