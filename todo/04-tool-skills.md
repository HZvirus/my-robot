# 04 · 工具生态与 Skills 沉淀体系

> JD 对应：Agent 可调用的多样化工具集（内部 API / 三方服务 / 脚本）；交互契约与错误语义；以 Skill 为单元沉淀业务能力，按需加载，跨业务线复用。

## 现状对齐（基于现有代码）

- **无工具/技能抽象**。`llm_client` 未使用 tools 参数（`llm_client.py:54`，`extra` 透传位 `:60`）。各 service 是硬编码能力，非「可调用工具」。
- 可沉淀为工具的现有能力：text-to-sql（见 `todo/text-to-sql.md`）；科室匹配（原 `departments.py` `match_departments`）与知识检索（原 `vector_store`）已随重构移除，需重建；挂号/医院信息（前端已有挂号入口）。
- 已有可复用的模式：懒加载单例（`auth_service.py:109` `auth_service`、`companion_service.py:228` `companion_service`）、RBAC 权限映射（`rbac.py` `ROLE_SCOPES`）。

## 目标

建立统一工具契约与 Skill 打包单元，沉淀业务能力，按需加载、权限可控、跨业务复用。

## 任务

### 1. 工具抽象与契约
- [ ] `app/services/agent/tools/` 包：`base.py`（`ToolBase`：name / description / parameters JSON Schema / invoke）
- [ ] 错误语义：`ToolError`(code/message/retryable)，与 06 可观测打通（工具成功率）
- [ ] OpenAI function-calling schema 自动生成（从 pydantic/类型）

### 2. 内置工具实现
- [ ] `tools/text_to_sql.py`（对应 `todo/text-to-sql.md`）
- [ ] `tools/kb_search.py`（封装重建后的向量检索，见 03）
- [ ] `tools/departments.py`（重建原 `departments.match_departments` 科室匹配）
- [ ] `tools/hospital_info.py`（挂号/科室查询）

### 3. 三方 / 脚本工具
- [ ] 外部 API 调用工具（带超时/重试，复用 `httpx` 模式如 `llm_client.py`）

### 4. Skill 沉淀与按需加载
- [ ] `Skill` = 相关工具 + 提示词 + 权限的打包单元
- [ ] `skill_registry.py`：按需加载，懒初始化（参考 `companion_service.py:228` 单例模式）
- [ ] 权限：Skill 绑定 RBAC role（对齐 `rbac.py` ROLE_SCOPES），实现跨业务复用

### 5. 错误语义与降级
- [ ] 工具失败兜底策略，单工具崩溃不影响整条链路

## 依赖

- 被 01（Agent 调用工具）调用；与 06（监控工具成功率）联动；text-to-sql 为首个落地工具。
