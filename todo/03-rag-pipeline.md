# 03 · RAG 知识检索全链路

> JD 对应：知识库及 RAG 全链路建设与调优 —— 文档切分、Embedding、混合检索（向量+关键词）、Rerank 重排、Query Rewrite，解决召回率瓶颈，提升可归因性，消除幻觉。

## 现状对齐（基于现有代码）

- **切分**：`text_splitter.py` 字符滑窗 + 段落感知（`split_text`），配置 `TRIAGE_CHUNK_SIZE=500/OVERLAP=80`（`config.py:86`）。仅按字符，无 Markdown 标题层级 / 表格切分。
- **Embedding**：bge-m3 via `embedding.py`（带 LRU 缓存 `embedding.py:9`），`embed_client`。
- **检索**：仅向量检索，`ScopedVectorStore.query` 跨 scope 取 top_k 后按余弦距离排序（`vector_store.py:165`、`:185`），`TRIAGE_TOP_K=4`。scope 物理隔离（`vector_store.py:132`）+ RBAC（`rbac.py` ROLE_SCOPES）。
- **上下文/归因**：`triage_service._format_context` 4000 字符预算 + 引用编号 `[i]`（`triage_service.py:205`），sources 回传前端（`:122`）。
- **入库**：`scripts/ingest_kb.py` 按 scope 批量入库。
- **无**：关键词检索/BM25、混合检索、Rerank、Query Rewrite。

## 目标

把单路向量检索升级为「Query Rewrite → 混合检索 → Rerank 精排 → 归因兜底」全链路，突破召回率瓶颈、消除幻觉。

## 任务

### 1. 切分增强
- [ ] `text_splitter.py`：支持 Markdown 标题层级切分、表格/列表感知；chunk metadata 带标题路径

### 2. 混合检索
- [ ] 新增关键词检索：BM25（`rank_bm25` 或 SQLite FTS5）索引 chunk 文本
- [ ] `app/services/retriever/` 包：`hybrid_retriever.py` 向量+关键词融合（RRF 或加权）
- [ ] 复用 scope 隔离模式（对齐 `ScopedVectorStore`）

### 3. Rerank 重排
- [ ] `reranker.py`：cross-encoder 重排（bge-reranker 等）；召回粗排 top-N → rerank 精排 top-K

### 4. Query Rewrite
- [ ] `query_rewrite.py`：历史相关指代消解 / 子问题分解（复用 `_load_history`）；多 query 并发检索

### 5. 归因与抗幻觉
- [ ] 强制引用：答案事实点可溯源 chunk（已有 sources，增强校验）
- [ ] 检索为空/低置信兜底（已有「暂无资料」`triage_service.py:207`，增加分数阈值过滤）

### 6. 调参与评测
- [ ] top_k / chunk_size / rerank 阈值标定（依赖 06 评测集）

## 依赖

- 复用 `embedding.py` / `vector_store.py` / `kb_loader.py`；调参依赖 06。
