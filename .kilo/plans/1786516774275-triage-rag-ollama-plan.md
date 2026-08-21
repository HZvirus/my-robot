# 智能导诊对话 (RAG over Ollama) 实施计划

## 目标
在 `apps/ai-service` 新增基于 RAG 的智能导诊对话能力：本地 Ollama 提供 LLM + 向量嵌入，医院自有知识库 (md/txt) 入库 ChromaDB，对外暴露 SSE 流式接口，`apps/h5-app1` 调用并展示。

## 已确认决策
- LLM: `qwen3:14b`；Embedding: `bge-m3`（1024 维，可配置）。
- 向量库: **ChromaDB**（本地持久化 + 元数据过滤）。
- 知识库来源: `knowledge/` 目录下 md/txt 文件 + 一次性入库脚本。
- 响应: **SSE 流式**（POST + fetch ReadableStream，前端非 EventSource）。
- 会话历史: **SQLite 持久化**（复用 SQLAlchemy）。
- 不引入 LangChain，保持现有 raw `httpx` 精简风格；分块用自写小工具。
- 新增独立端点 `/api/triage/*`，**不改动**现有 `/api/chat`。
- 导诊 UI 放 `h5-app1`，新增 `/triage` 路由。

## 模型与端点约定 (Ollama)
- Base: `http://localhost:11434`，走 OpenAI 兼容接口：
  - 嵌入: `POST {base}/v1/embeddings`，body `{model, input}`，无需真实 key（发 `Bearer ollama` 占位）。
  - 对话流: `POST {base}/v1/chat/completions`，`stream: true`，按 SSE `data: {choices:[{delta:{content}}]}` 解析，末尾 `data: [DONE]`。
- 前置条件: `ollama serve` 已运行且 `qwen3:14b`、`bge-m3` 已 pull（已确认存在）。

## 数据流 (单轮)
1. 前端 POST `/api/triage/chat` `{message, conversation_id?}`，响应 `text/event-stream`。
2. 后端：取/生成 `conversation_id` → 从 SQLite 取最近 N 条历史 → `embed(query)` → ChromaDB `query(top_k)` → 拼 system+context+history+user → Ollama 流式生成。
3. SSE 事件序列：
   - `data: {"conversation_id":"..."}` (首帧)
   - `data: {"delta":"..."}` (多次)
   - `data: {"sources":[{"file","text"}]}` (引用片段，可选)
   - `data: [DONE]`
4. 流式累积完整回复，结束后写入 SQLite `Message`（user + assistant 各一条）。
5. 客户端断开：捕获 `asyncio.CancelledError`，已累积部分仍落库（标记 `interrupted`）。

## 后端任务 (apps/ai-service)

### 配置 — `app/core/config.py` + `.env.example`
新增字段：
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen3:14b
OLLAMA_EMBED_MODEL=bge-m3
EMBEDDING_DIM=1024
CHROMA_PERSIST_DIR=./data/chroma
KB_DIR=./knowledge
TRIAGE_TOP_K=4
TRIAGE_MAX_HISTORY=6
TRIAGE_CHUNK_SIZE=500
TRIAGE_CHUNK_OVERLAP=80
```
保留现有 `AI_*` 字段不动。

### 依赖 — `pyproject.toml`
新增 `chromadb>=0.5.0`。numpy 由 chromadb 间接带入。不新增 langchain/sse-starlette（用原生 `StreamingResponse`）。

### 新文件
- `app/services/ollama_client.py`
  - `async embed(texts: list[str]) -> list[list[float]]`（批处理，调 `/v1/embeddings`）。
  - `async chat_stream(messages: list[dict]) -> AsyncIterator[str]`（调 `/v1/chat/completions` stream，逐 delta yield 文本）。
  - 复用一个全局 `httpx.AsyncClient`（或按调用创建，timeout=120）。
- `app/services/embedding.py`：封装 embed，缓存可选；提供 `embed_one(text)`。
- `app/services/vector_store.py`：ChromaDB 封装
  - `get_collection()` 懒加载/创建 `hospital_kb`（`metadata={"hnsw:space":"cosine"}`）。
  - `upsert(ids, documents, metadatas, embeddings)`。
  - `query(embedding, n_results=TRIAGE_TOP_K, where=None) -> list[dict]`（返回 `{document, metadata, distance}`）。
- `app/services/kb_loader.py`：读 `KB_DIR` 下 `*.md`/`*.txt`
  - 按标题/空行切段，再按 `TRIAGE_CHUNK_SIZE`/`OVERLAP` 字符滑窗切块。
  - 每块 metadata: `{"file": 文件名, "index": 序号}`。
- `app/services/text_splitter.py`：纯函数 `split_text(text, size, overlap) -> list[str]`。
- `app/services/triage_service.py`：
  - `async stream_answer(message, conversation_id) -> AsyncIterator[dict]`（yield 上述 SSE 事件 dict）。
  - system prompt：导诊助手身份 + 仅依据提供的医院资料回答 + 推荐就诊科室 + 不下诊断/不处方 + 超出资料则说明并建议挂号/咨询导诊台。
  - 上下文拼接：把检索片段编号注入 system。
  - 历史：取 `TRIAGE_MAX_HISTORY` 条（role/content）。
  - 流式结束后写库。
- `app/db/models.py`：SQLAlchemy
  - `Conversation(id:str PK, created_at)`
  - `Message(id:str PK, conversation_id FK, role, content, sources:JSON, interrupted:bool, created_at)`
  - 在 `session.py` 或 `main.py` lifespan 调 `Base.metadata.create_all`。
- `app/api/routes/triage.py`：
  - `POST /api/triage/chat` → `StreamingResponse(generator, media_type="text/event-stream")`，把 dict 序列化为 `data: {json}\n\n`。
  - `GET /api/triage/history/{conversation_id}` → 返回该会话消息列表。
  - `GET /api/triage/conversations` → 会话列表（id + 首条消息 + 时间），可选但便于前端侧栏。
- `scripts/ingest_kb.py`：CLI 入库
  - `kb_loader.load()` → `embed` 批量 → `vector_store.upsert`（按 `file+index` 幂等 id）。
  - 入口 `python -m scripts.ingest_kb` 或 `python scripts/ingest_kb.py`。
  - 在 `pyproject.toml` 加 `[project.scripts]` 可选。

### 现有文件改动
- `app/main.py`：lifespan 中 `Base.metadata.create_all(engine)`；`include_router(triage.router, prefix="/api", tags=["triage"])`。
- `app/api/routes/__init__.py`：导出 triage（如需）。
- `.env.example`：补 OLLAMA_* 等字段。
- `README.md`：补“导诊/知识库入库”章节与运行命令。

### 知识库样例 (便于端到端跑通，用户后续替换为真实资料)
- `knowledge/departments.md`（科室清单与简介）
- `knowledge/hospital_info.md`（地址/电话/工作时间/交通）
- `knowledge/symptoms.md`（常见症状→科室映射）
- `knowledge/registration.md`（挂号/缴费/就诊流程）

## 前端任务 (apps/h5-app1)

### 共享类型 — `packages/shared-types/src/index.ts`
新增：
```ts
export interface TriageSource { file: string; text: string }
export interface TriageStreamEvent {
  conversationId?: string
  delta?: string
  sources?: TriageSource[]
  done?: boolean
  error?: string
}
export interface TriageRequest { message: string; conversationId?: string }
```

### 新文件
- `src/api/triage.ts`：
  - `streamTriage(req, handlers: { onEvent, onError, onClose })`：用 `fetch('/api/triage/chat', {method:POST, body})` + `response.body.getReader()` + `TextDecoder`，按行解析 `data: {...}`，调用 `onEvent`。
- `src/stores/triage.ts` (Pinia)：`messages`、`conversationId`、`streaming`、`sources`、`send(text)`、`loadHistory(id)`。
- `src/views/TriageView.vue`：导诊对话 UI
  - 消息列表（用户/助手气泡），助手消息流式逐字渲染。
  - 输入框 + 发送按钮（`@my-robot/ui` 的 BaseButton/LoadingSpinner）。
  - 引用来源折叠展示。
  - 快捷提问 chips（如“肚子疼挂什么科”）。
  - 移动端 H5 适配（已有 `assets/main.css` 风格）。

### 现有文件改动
- `src/router/index.ts`：新增 `{ path: '/triage', name: 'triage', component: () => import('@/views/TriageView.vue') }`，首页加入口链接。
- `src/views/HomeView.vue`：加“智能导诊”入口（若合适）。

## 验证
1. `cd apps/ai-service; pip install -e ".[dev]"` 成功（重点 ChromaDB 在 Windows 安装）。
2. `ollama serve` 运行；`python scripts/ingest_kb.py` 输出入库块数，`data/chroma` 生成。
3. 单测 `tests/test_triage.py`：
   - `text_splitter` 切块数/边界。
   - `triage_service` 用假 `OllamaClient`（mock embed 返回固定向量、chat_stream yield 固定 deltas）验证 SSE 事件序列与落库。
   - `test_health.py` 仍通过。
4. 手动 `curl -N -X POST localhost:8000/api/triage/chat -H "Content-Type: application/json" -d '{"message":"肚子疼挂什么科"}'` 看到流式 `data:`。
5. `pnpm dev` 后访问 `http://localhost:5173/triage` 端到端联调（vite 已代理 `/api` → 8000）。
6. `ruff check .` 与 `mypy app` 通过；前端 `pnpm --filter @my-robot/h5-app1 typecheck` + `lint` 通过。

## 风险与回退
- **ChromaDB Windows 安装**：依赖 onnxruntime 等，可能慢/失败。回退方案：改用 `faiss-cpu + numpy`，向量与元数据存 SQLite（`vector_store.py` 接口不变，换实现）。
- **嵌入维度不匹配**：`bge-m3` 为 1024；若换模型须同步 `EMBEDDING_DIM` 并清空 `data/chroma` 重新入库。
- **SSE + POST**：浏览器 `EventSource` 不支持 POST，故前端用 `fetch` 流式读取（已在方案中）。
- **上下文超长**：`qwen3:14b` 上下文有限；限制 `TRIAGE_MAX_HISTORY` 与检索片段长度，拼接前裁剪。
- **流式中途断开**：捕获取消异常，落库已生成部分并标记 `interrupted`。
- **真实资料格式**：当前仅支持 md/txt；若后续需要 PDF/Word，再引入 `pypdf`/`python-docx` 并扩展 `kb_loader`（明确为后续范围）。

## 明确不在本次范围
- 用户鉴权 / 多租户。
- 后台上传与管理后台（走文件 + 脚本即可）。
- PDF/Word/Excel 解析。
- 语音输入、TTS。
- 对接真实 HIS/挂号系统。
