# 架构文档

## 1. 服务拓扑

```
                           ┌──────────────────────────┐
                           │     H5 医院 24寸 / 家庭 7寸  │
                           │  (Vue3 + Vite + ui-shared) │
                           └──────────────┬───────────┘
                              REST /api/*  │  WS /ws/chat
                                           ▼
                                  ┌────────────────┐
                                  │   Kong 3.x     │  DB-less (kong.yml)
                                  │  :8000 proxy   │  CORS + rate-limit(Redis)
                                  └───────┬────────┘
            ┌──────────────┬───────────────┼───────────────┬──────────────┐
            ▼              ▼               ▼               ▼              ▼
       user-tenant    dialog-engine   model-gateway    rag-engine    task-executor
        :8200            :8100           :8300           :8400          :8500
        Postgres         Redis+PG        adapters        pgvector       Redis Stream
                         ↑ calls ────────┘  └── calls ───┘              │
                         │                                                 ▼
                         └──────────── Redis Stream task:execute ──► HAL ─► MQTT
                                                                        ▲
                                                                  mock-robot (sub)
                                                       EMQX 5 :1883 / :8083 (WS)
```

## 2. 端口与服务

| 服务 | 容器端口 | 说明 |
|---|---|---|
| Kong gateway | 8000 / 8001 | 代理 / API |
| user-tenant | 8200 | 用户/租户/鉴权/Feedback |
| dialog-engine | 8100 | 对话编排 + WS + 场景配置 + 反馈 |
| model-gateway | 8300 | 统一 LLM 接口 + 适配器 |
| rag-engine | 8400 | 知识库检索 (pgvector) |
| task-executor | 8500 | 动作 -> MQTT 指令 |
| mock-robot | — | 订阅 `robot/+/+/cmd` 打日志 |
| postgres (pgvector) | 5432 | 共享单库 `myrobot` |
| redis | 6379 | 会话状态 + 任务流 + 限流 |
| emqx | 1883 / 8083 / 18083 | MQTT / MQTT-over-WS / 控制台 |
| h5-hospital | 5173 | Vite dev |
| h5-home | 5174 | Vite dev |

## 3. 接口契约

### 3.1 认证（user-tenant，Kong 路由 `/api/auth/*`）

- `POST /api/auth/login` -> `{phone, password, tenant_id?}` -> `{access_token, token_type, expires_in, user, tenant}`
- `POST /api/auth/refresh` -> 旧 token -> 新 token
- JWT claim: `sub`(user_id) `tenant_id` `scene`(hospital|home) `role` `exp`

### 3.2 用户/租户（`/api/users/*`、`/api/tenants/*`）

- `GET /api/users/me` `GET /api/users` `POST /api/users`（admin）
- `GET /api/tenants` `POST /api/tenants`（admin）
- 所有查询按 JWT 中 `tenant_id` 强制隔离

### 3.3 模型网关（`/v1/*`，Kong 不 strip）

- `POST /v1/chat` -> OpenAI 风格：`{messages, model?, stream, scene}`；`stream=true` 返回 SSE `data: {"choices":[{"delta":{"content":"..."}}]}\n\n`，结束 `data: [DONE]`
- `GET /v1/models` -> `{data:[{id}]}`
- 路由按 `scene` 选模型组，不可用回退 `skeleton_mock`

### 3.4 RAG（`/api/collections` 等，Kong strip `/api`）

- `POST /collections` `GET /collections`
- `POST /documents` `{collection, text, metadata}` -> 分块 + 向量化
- `POST /retrieve` `{collection, query, top_k}` -> `{results:[{text, metadata, score}]}`
- 默认离线确定性 embedding（dim=256），预留 sentence-transformers provider

### 3.5 任务执行（`/api/tasks/*`）

- `POST /tasks` `{type, params, tenant_id?, device_id?}` -> 入 Redis Stream `task:execute`
- `GET /tasks/{id}` -> 状态（pending/processing/done + result）

### 3.6 反馈（dialog-engine `/api/feedback`）

- `POST /api/feedback` `{session_id, message_id, score(1|-1)}` -> 写 Feedback 表

## 4. WebSocket 消息协议（`/ws/chat?token=<jwt>`）

客户端 -> 服务端:

```json
{"type": "chat", "text": "你好"}
{"type": "ping"}
```

服务端 -> 客户端（统一 `{type, session_id?, payload}`）:

| type | payload | 说明 |
|---|---|---|
| `status` | `{state, event?, message?}` | 连接/状态/安全事件 |
| `token` | `{delta}` | 流式 token |
| `message` | `{message_id, text, scene}` | 完整回复 |
| `action` | `{id, type, params, status}` | 抽取到的动作（已入任务流） |
| `error` | `{message}` | 错误 |

会话状态机：`awaiting_input -> processing -> streaming -> awaiting_task -> awaiting_input`

## 5. 场景配置

| 字段 | hospital | home |
|---|---|---|
| model_group | hospital_cloud | home_edge |
| rag_mode | force | on_demand |
| rag_collections | hospital_dept, drug_manual, insurance_policy | elder_health, home_care |
| asr_profile | noisy | quiet |
| safety_policy | escalate | soothe |
| output_format | structured | natural |

场景配置由 `dialog-engine/scene_config/*.yaml` 驱动，编排逻辑从配置读取而非硬编码。

## 6. 模型组配置（`model_groups.yaml`）

| 组 | 适配器 | 用途 |
|---|---|---|
| skeleton_mock | mock | 离线默认，真异步 SSE 流式 |
| hospital_cloud | openai_compat | DeepSeek/云端（需 API key，缺则回退 mock） |
| home_edge | ollama | qwen2.5-1.5b 本地 |

`scene_routes: hospital->hospital_cloud, home->home_edge`，`default_group: skeleton_mock`。

## 7. HAL 与机器人控制

- `RobotDriver` ABC：`move_forward/move_backward/rotate/speak/play_media/stop` + 通用 `execute(action)`
- 实现：`mock_driver`（日志）、`ubt_driver`/`xiaomi_driver`（NotImplementedError 占位）
- 注册表 `get_driver(name)`，默认 `mock`

## 8. 技能插件（libs/skills）

`Skill` 基类（name/description/args_schema/handler）+ `@skill` 装饰器 + 注册表。
示例：`get_dept_schedule`、`weather_broadcast`（stub）。dialog-engine 注入注册表供后续 Function Calling。

## 9. Redis Stream 与 MQTT 协议

- 任务流：`XADD task:execute * payload=<json>`，消费组 `task-executors`
- 动作 schema：`{id, type, params, tenant_id, device_id, scene}`
- MQTT 发布：`robot/{tenant_id}/{device_id}/cmd` payload `{id, type, params, status}`
- 状态回执：`robot/+/+/state`，task-executor 订阅
- mock-robot 订阅 `robot/+/+/cmd` 打日志

## 10. 数据库表

| 表 | 服务 | 关键字段 |
|---|---|---|
| tenants | user-tenant | id, name, scene, config(jsonb) |
| users | user-tenant | id, tenant_id, name, phone, role, password_hash |
| feedback | user-tenant / dialog-engine | session_id, user_id, tenant_id, message_id, score（RLHF 数据源） |
| rag_collections | rag-engine | name, description |
| rag_documents | rag-engine | collection_id, chunk, embedding(vector 256), metadata |

## 11. 路线图映射（不在骨架范围）

| 能力 | 状态 |
|---|---|
| 真实云端 LLM 计费 | openai_compat 适配器可接，计费留接口 |
| 真实 ASR | asr_profile 配置占位 |
| 端侧 NPU (RKNN) | npu 适配器 NotImplementedError 占位 |
| 真机驱动 | HAL ABC + mock，ubt/xiaomi 占位 |
| ClickHouse 数据中台 | Feedback 表为数据源，迁移留接口 |
| K8s manifests | 镜像结构保持一致，便于迁移 |
| 联邦学习 / OTA | 文档占位 |
| 语音合成 / 导航 | 不在范围 |
