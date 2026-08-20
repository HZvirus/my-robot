# 待办：AI 自然语言转 SQL（Text-to-SQL）

> 状态：待开始
> 相关模块：`apps/ai-service`
> 复用：`app/services/llm_client.py`（OpenAI 兼容，本地 Ollama 或云端 LLM）

## 目标

支持用户用自然语言查询业务数据，由 LLM 翻译为只读 SQL，在 `app.db.models`
现有模型（`User` / `Conversation` / `Message`）上执行后返回结果与自然语言摘要。

示例：
- 「今天有多少个导诊会话」→ `SELECT COUNT(*) FROM conversations WHERE date(created_at)=date('now')`
- 「最近 10 条用户消息」→ `SELECT id, content, created_at FROM messages ORDER BY created_at DESC LIMIT 10`

## 范围与任务

### 1. 服务层
- [ ] 新建 `app/services/text_to_sql_service.py`
- [ ] 用 `llm_client` 完成自然语言 → SQL 翻译
  - [ ] 注入表结构 schema（基于 `app/db/models.py` 自动生成 DDL 或手写 schema 摘要）
  - [ ] 系统提示词：只生成 `SELECT`，禁止 `INSERT/UPDATE/DELETE/DROP` 等，SQLite 方言
  - [ ] 解析并校验 LLM 输出（抽取 SQL，剥离 markdown 代码块）
- [ ] 执行层
  - [ ] 复用 `app/db/session.py` 的 `engine`，使用只读会话执行
  - [ ] 表白名单：仅允许 `users` / `conversations` / `messages`
  - [ ] 行数上限（如 `LIMIT 100` 兜底），超长字段截断
  - [ ] 用 `sqlparse`/AST 或正则做二次校验，拒绝多语句与写操作

### 2. 数据模型与路由
- [ ] 新建 DTO `app/models/text_to_sql.py`（请求：`question`；响应：`sql`、`rows`、`summary`）
- [ ] 新建路由 `app/api/routes/text_to_sql.py`，`POST /api/text-to-sql/query`
  - [ ] 复用 `app/api/deps.py` 鉴权与角色（参考 RBAC，仅允许有权限角色）
  - [ ] 失败兜底：翻译失败 / 执行报错 / 超时，返回结构化错误
- [ ] 在 `app/main.py` 注册路由（`include_router`，对齐 `main.py:37-39`；`app/api/routes/__init__.py` 当前为空）

### 3. 自然语言摘要
- [ ] 执行结果回喂 LLM，生成中文摘要（表格 → 一两句话）
- [ ] 可选：流式返回摘要（SSE，沿用 `_parse_delta` 解析风格）

### 4. 配置
- [ ] `app/core/config.py` 增加开关与限制项
  - `TEXT_TO_SQL_ENABLED`、`TEXT_TO_SQL_MAX_ROWS`、`TEXT_TO_SQL_TIMEOUT`
- [ ] `.env.example` 同步示例

### 5. 测试
- [ ] `apps/ai-service/tests/` 增加 `test_text_to_sql_service.py`
  - [ ] 翻译正确性（mock `llm_client`）
  - [ ] 安全拦截：拒绝写操作、多语句、非白名单表
  - [ ] 边界：空结果、超长行数截断

### 6. 前端（可选，后续）
- [ ] `apps/h5-app2` 或管理端增加「自然语言查询」入口，调用新接口并渲染表格

## 安全约束（必须）

- 只读：仅允许单条 `SELECT`，禁用一切写/DDL 操作
- 表白名单 + 字段裁剪，避免泄露 `users.token_hash` 等敏感列
- 默认行数上限与超时
- 生产环境 SQLite 以只读模式打开（`file:...?mode=ro`）或独立只读副本

## 风险与备注

- 小模型（本地 Ollama）SQL 生成能力有限，需强 schema 提示 + few-shot 示例 + 输出校验
- SQLite 函数差异（`date()`/`strftime()`）需在提示词中说明
- 后续可扩展到知识库元数据等只读视图
