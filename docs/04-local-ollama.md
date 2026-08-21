# 04 · 使用本地模型（Ollama）

通用聊天、健康陪伴、智能导诊的对话生成，以及导诊的知识库向量化，全部走**本地 Ollama**，不引入 LangChain / SDK，只通过其 **OpenAI 兼容接口**用 `httpx` 直连。封装在 `app/services/ollama_client.py`。

## 1. 模型

| 用途 | 模型 | 说明 |
| --- | --- | --- |
| 对话生成 | `qwen3:14b`（`OLLAMA_LLM_MODEL`） | 中文质量较好，上下文有限 |
| 文本嵌入 | `bge-m3`（`OLLAMA_EMBED_MODEL`） | 输出 1024 维向量（`EMBEDDING_DIM`） |

## 2. 前置条件

```bash
ollama serve                    # 启动本地服务（默认 11434）
ollama pull qwen3:14b
ollama pull bge-m3
```

更换嵌入模型时必须同步 `EMBEDDING_DIM`，并清空 `data/chroma` 后重新入库。

## 3. `OllamaClient` 两个核心方法

### 3.1 嵌入 `embed(texts)`

`POST {base}/v1/embeddings`，body `{model, input: [文本...]}`，返回 `data[i].embedding`。服务端忽略鉴权头，但仍发送占位 `Authorization: Bearer ollama`：

```python
async def embed(self, texts: list[str]) -> list[list[float]]:
    headers = {"Authorization": "Bearer ollama", "Content-Type": "application/json"}
    payload = {"model": self.embed_model, "input": texts}
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        resp = await client.post(f"{self.base_url}/v1/embeddings", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["data"]]
```

`embedding.py` 的 `EmbeddingService` 包装了它，`embed_one(text)` 带 256 条 LRU 缓存（导诊每次查询同一句话不会重复计算）。

### 3.2 流式对话 `chat_stream(messages)`

`POST {base}/v1/chat/completions`，`stream: true`。响应是 SSE 行，逐行解析 `data: {choices:[{delta:{content}}]}`，遇到 `data: [DONE]` 结束：

```python
async def chat_stream(self, messages):
    payload = {"model": self.llm_model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        async with client.stream("POST", f"{self.base_url}/v1/chat/completions",
                                 headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                token = _parse_delta(line)   # 跳过空行 / [DONE] / 无 content 的帧
                if token is not None:
                    yield token
```

`_parse_delta` 只关心 `choices[0].delta.content`（字符串），其余一律忽略。

## 4. 知识库入库（RAG 前置）

知识库是 `knowledge/` 下的 md/txt 文件，入库脚本 `scripts/ingest_kb.py`：

```bash
cd apps/ai-service
python -m scripts.ingest_kb      # 或 install 后直接 ingest-kb
```

流程：

1. `kb_loader.load_kb()`：读取 `*.md/*.txt`，用 `text_splitter.split_text`（`TRIAGE_CHUNK_SIZE=500`，`TRIAGE_CHUNK_OVERLAP=80`）分块，id 为 `{文件名}#{序号}`（幂等，可重复执行覆盖）。
2. `ollama_client.embed(...)` 批量计算向量（每次 32 条）。
3. `vector_store.upsert(...)` 写入 ChromaDB 持久化目录 `data/chroma`。

## 5. 向量库（`app/services/vector_store.py`）

- 集合 `hospital_kb`（`CHROMA_COLLECTION`），`metadata={"hnsw:space":"cosine"}` 用余弦距离。
- `query(embedding, n_results=TRIAGE_TOP_K)` 返回 `{document, metadata, distance}` 列表。
- 定义了 `VectorStoreProtocol`，`ChromaVectorStore` 为其实现；如需换 FAISS/SQLite 只需换实现、接口不变。
- **缓存失效重试**：若服务运行期间另一进程重新入库，ChromaDB 缓存的段元数据会过期（报 `Nothing found on disk`）。`query()` 捕获异常后失效并重建集合对象重试一次，因此支持「服务不重启也能看到新入库数据」。

## 6. 上下文预算

`qwen3:14b` 上下文有限，导诊做了两层限制：

- 历史只取最近 `TRIAGE_MAX_HISTORY = 6` 条；
- 检索片段注入 system 时累计不超过 `CONTEXT_BUDGET = 4000` 字符，超出截断（`triage_service._format_context`）。

## 7. 全部接口均走本地模型

chat / companion / triage 三个流式接口，以及旧的兼容接口 `POST /api/chat`（`services/ai_service.py`），全部走本地 Ollama，不依赖任何云端模型或 API Key（`.env` 中已无 `AI_API_*` 配置）。
