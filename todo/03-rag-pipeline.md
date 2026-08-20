# 03 · RAG 知识检索全链路

> JD 对应：知识库及 RAG 全链路建设与调优 —— 文档切分、Embedding、混合检索（向量+关键词）、Rerank 重排、Query Rewrite，解决召回率瓶颈，提升可归因性，消除幻觉。

## 现状对齐（基于现有代码）

- **切分 / Embedding / 向量检索已移除**：`text_splitter.py`、`embedding.py`、`vector_store.py`（含 `ScopedVectorStore`）均不在 `app/services/`；`scripts/ingest_kb.py` 仍存在但 import 已删模块（`kb_loader` / `embed_client` / `get_vector_store`），当前不可运行。本模块为**从零重建**而非增强。
- **权限模型仍存**：`app/core/rbac.py` 保留 `ROLE_SCOPES:18`（patient/nurse/doctor/admin → scope 集合）与 `scopes_for:44`，scope 物理隔离语义可复用。
- **归因基座仍存**：`Message.sources`（`db/models.py:50`）保留引用回传字段。
- **无**：关键词检索/BM25、混合检索、Rerank、Query Rewrite，且现无任何检索/embedding 实现。

## 目标

把单路向量检索升级为「Query Rewrite → 混合检索 → Rerank 精排 → 归因兜底」全链路，突破召回率瓶颈、消除幻觉。

## 任务

### 1. 切分增强
- [ ] `text_splitter.py`：支持 Markdown 标题层级切分、表格/列表感知；chunk metadata 带标题路径

### 2. 混合检索
- [ ] 新增关键词检索：BM25（`rank_bm25` 或 SQLite FTS5）索引 chunk 文本
- [ ] `app/services/retriever/` 包：`hybrid_retriever.py` 向量+关键词融合（RRF 或加权）
- [ ] 复用 scope 隔离语义（对齐 `rbac.py` `ROLE_SCOPES` / `scopes_for`）

### 3. Rerank 重排
- [ ] `reranker.py`：cross-encoder 重排（bge-reranker 等）；召回粗排 top-N → rerank 精排 top-K

### 4. Query Rewrite
- [ ] `query_rewrite.py`：历史相关指代消解 / 子问题分解（复用 `companion_service.py:125` `_load_history` 思路）；多 query 并发检索

### 5. 归因与抗幻觉
- [ ] 强制引用：答案事实点可溯源 chunk（`Message.sources` 已存于 `db/models.py:50`，增强校验）
- [ ] 检索为空/低置信兜底（原 triage 的「暂无资料」分支已随重构移除，需重建），增加分数阈值过滤

### 6. 调参与评测
- [ ] top_k / chunk_size / rerank 阈值标定（依赖 06 评测集）

## 依赖

- RAG 栈（切分/embedding/检索/入库）已移除需重建；复用 `rbac.py` scope 模型与 `Message.sources`；调参依赖 06。
