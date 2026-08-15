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

相关环境变量见 `.env.example`（`OLLAMA_*`、`LLM_*`、`EMBED_*`、`TRIAGE_*`、`CHROMA_*`、`KB_DIR`、`EMBEDDING_DIM`）。更换嵌入模型时须同步 `EMBEDDING_DIM` 并清空 `data/chroma` 重新入库。

### 模型后端切换（Ollama / vLLM / 通义 API 等）

`ai-service` 通过统一的 OpenAI 兼容客户端调用模型，**改 `.env` 即可切换后端，无需改代码**。

- 生成（对话 / 陪伴 / 导诊）走 `LLM_*`，检索嵌入走 `EMBED_*`，两者可独立配置不同后端。
- `LLM_*` / `EMBED_*` 为空时回退到 `OLLAMA_*`（默认本地 Ollama，开发态零配置）。
- `LLM_BASE_URL` / `EMBED_BASE_URL` 写到 `/v1` 为止或不写均可（内部自动补全）。
- `LLM_API_KEY` 为空时发送占位鉴权（Ollama 忽略）；接通义 / 其它云 API 时填真实 key。

| 后端 | LLM_BASE_URL | LLM_MODEL | 说明 |
|------|--------------|-----------|------|
| 本地 Ollama | `http://localhost:11434` | `qwen2.5:7b` | 开发默认，`LLM_*` 留空 |
| 自托管 vLLM | `http://<host>:8000` | `Qwen/Qwen2.5-7B-Instruct` | 生产自建，换 Ollama 为 vLLM 提升吞吐 |
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 生产调通义 API，填 `LLM_API_KEY` |

> 切换嵌入模型（如本地 `bge-m3` → 通义 `text-embedding-v3`）后，须同步 `EMBEDDING_DIM` 并清空 `data/chroma` 重新执行 `ingest-kb`。
## 设备鉴权（会话归属）

会话接口（/api/chat*、/api/companion/*、/api/triage/chat、/api/triage/history/*、/api/triage/conversations）与 /api/smart-tts/* 需要 Authorization: Bearer <device-token>。

- POST /api/auth/device：客户端首次生成 16-128 位设备令牌，换取稳定 user_id；服务端只存 SHA-256 哈希，数据库泄露不暴露原始凭据。
- 会话按 owner_id 隔离：访问他人会话返回 404（不暴露存在性），会话列表仅返回本人会话。
- 浏览器 WebSocket 无法附加请求头，/api/smart-tts/ws 通过查询参数 ?token= 鉴权。

## 超拟人 TTS（WS 桥接）

/api/smart-tts/stream-text（整段缓冲）已由双向 WebSocket 桥接 /api/smart-tts/ws 取代，实现真正的增量合成：

1. 首帧 JSON 传合成参数 {voice, speed, volume, pitch, sampleRate, oralLevel}；
2. 随后按 {"text": "..."} 增量推送，{"end": true} 结束；
3. 服务端回 {"audio": "<base64>"}* 与 {"done": true}。

浏览器直连讯飞（快速版）仍走 GET /api/smart-tts/ws-url 获取签名地址。
