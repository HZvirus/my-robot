# AI Service

Python AI backend service (FastAPI) for the my-robot monorepo.

## Structure

```
ai-service/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── api/                 # HTTP route handlers
│   │   ├── deps.py          # Shared dependencies
│   │   └── routes/          # Route modules
│   ├── core/                # Config, logging, security
│   ├── models/              # Pydantic schemas
│   ├── services/            # Business / AI logic
│   └── db/                  # Database session & models
└── tests/
```

## Setup

```bash
cd apps/ai-service
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

## 通用对话（SSE 流式 + 上下文）

基于本地 Ollama（`qwen2.5:7b`，同智能导诊）的流式对话接口，会话自动持久化于 SQLite。

### 接口

- `POST /api/chat/stream`：SSE 流式对话。请求 `{message, conversationId?}`，事件依次为 `conversationId`、多个 `delta`、`done`，末尾 `data: [DONE]`。
- `GET /api/chat/history/{conversation_id}`：会话消息列表。
- `GET /api/chat/conversations`：会话列表（id + 首条消息 + 时间）。

带上 `conversationId` 即可继续上一次对话（自动携带最近 `CHAT_MAX_HISTORY` 条消息作为上下文）。

## 健康陪伴（SSE 流式 + 上下文）

面向 C 端用户的健康陪伴聊天，以「小安」人设提供健康科普、情绪陪伴与生活方式建议（不诊断、不开药，紧急症状提醒就医）。同样基于本地 Ollama（`qwen2.5:7b`），会话自动持久化于 SQLite。

### 接口

- `POST /api/companion/chat`：SSE 流式对话。请求 `{message, conversationId?}`，事件依次为 `conversationId`、多个 `delta`、`done`，末尾 `data: [DONE]`。
- `GET /api/companion/history/{conversation_id}`：会话消息列表。
- `GET /api/companion/conversations`：会话列表（id + 首条消息 + 时间）。

带上 `conversationId` 即可继续上一次对话（自动携带最近 `COMPANION_MAX_HISTORY` 条消息作为上下文）。

## 智能导诊（RAG over Ollama）

基于本地 Ollama（`qwen2.5:7b` 生成 + `bge-m3` 嵌入）与 ChromaDB 向量库的知识库问答接口，独立于现有 `/api/chat`。

### 前置条件

- `ollama serve` 已运行，且已 pull 模型：
  ```bash
  ollama pull qwen2.5:7b
  ollama pull bge-m3
  ```

### 入库知识库

把医院资料（`.md` / `.txt`）放入 `knowledge/`，然后执行：

```bash
python -m scripts.ingest_kb
# 或
ingest-kb
```

输出入库块数，向量数据持久化在 `data/chroma`。重复执行按 `文件#序号` 幂等覆盖，可安全重跑。

### 接口

- `POST /api/triage/chat`：SSE 流式导诊。请求 `{message, conversationId?}`，事件依次为 `conversationId`、`sources`、多个 `delta`、`done`，末尾 `data: [DONE]`。
- `GET /api/triage/history/{conversation_id}`：会话消息列表。
- `GET /api/triage/conversations`：会话列表（id + 首条消息 + 时间）。

会话与消息持久化于 SQLite（复用 `DATABASE_URL`）；流式中断时已生成部分会落库并标记 `interrupted`。

### 配置

相关环境变量见 `.env.example`（`OLLAMA_*`、`TRIAGE_*`、`CHROMA_*`、`KB_DIR`、`EMBEDDING_DIM`）。更换嵌入模型时须同步 `EMBEDDING_DIM` 并清空 `data/chroma` 重新入库。