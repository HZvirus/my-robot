# 机器人平台 Monorepo 骨架（医院 24寸 + 家庭 7寸）

全架构骨架：6 个后端微服务域（Kong 网关 + User/Tenant + Dialog Engine + Model Gateway + RAG Engine + Task Executor）、2 个 H5 应用（医院大屏 / 家庭小屏）、端到端聊天链路可离线跑通。

> 详见 `docs/architecture.md`。

## 目录结构

```
my-robot/
├── backend/      # Python 3.12 + FastAPI + uv workspaces（5 服务 + 3 共享库）
├── frontend/     # Vue 3 + Vite + TS + pnpm workspaces（2 应用 + 2 包）
├── deploy/       # docker-compose + Kong(DB-less) + .env
├── docs/         # 架构文档
└── scripts/      # dev.ps1 / dev.sh
```

## 技术栈

| 项 | 选型 |
|---|---|
| 后端 | Python 3.12 + FastAPI + uv workspaces |
| 前端 | Vue 3 + Vite + TypeScript + pnpm |
| 网关 | Kong 3.x（DB-less，`kong.yml`） |
| 数据 | PostgreSQL 16 + pgvector、Redis 7、EMQX 5（MQTT over WebSocket） |
| 编排 | Docker Compose |

## 快速启动

### 一键（Docker + 前端 dev）

PowerShell:

```powershell
.\scripts\dev.ps1
```

Bash / WSL:

```bash
./scripts/dev.sh
```

脚本会：`docker compose up -d --build`（含 Kong/PG/Redis/EMQX/5 后端服务/mock-robot）+ `pnpm install` + 启动两个 H5 dev server。

### 后端单独

```powershell
cd backend
uv sync                 # 安装所有 workspace 成员
uv run pytest           # 跑全部后端单测
uv run python -m user_tenant.main      # 单进程起 user-tenant（端口 8200）
uv run python -m dialog_engine.main    # 对话编排（8100）
```

### 前端单独

```powershell
cd frontend
pnpm install
pnpm dev:hospital   # http://localhost:5173 （医院大屏）
pnpm dev:home       # http://localhost:5174 （家庭小屏）
pnpm build          # 类型检查 + 构建
```

## 种子账号（离线可登录）

| 租户 | 场景 | 手机号 | 密码 |
|---|---|---|---|
| XX医院 | hospital | 13800000001 | 123456 |
| 张爷爷家 | home | 13800000002 | 123456 |

## 端到端验收（见 `docs/architecture.md`）

1. `docker compose up -d` 后所有服务健康
2. 种子租户登录拿 JWT：`POST /api/auth/login`
3. H5 登录后发「你好」，页面流式出现回复 token
4. 发「今天天气」→ mock 模型返回动作 → 前端动作卡片 + mock-robot 日志出现 MQTT cmd
5. hospital 场景发「癌症」→ 触发 `escalate`；home 场景触发 `soothe`
6. 点赞/点踩写入 Feedback 表
7. 后端 `uv run pytest` 通过；前端 `pnpm build` 通过

## 明确不在本次范围

真实云端 LLM 计费、真实 ASR、端侧 NPU 推理、真机驱动、ClickHouse 数据中台、K8s manifests、联邦学习与 OTA、语音合成与导航。这些仅留文档与接口占位。
