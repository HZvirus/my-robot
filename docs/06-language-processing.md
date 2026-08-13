# 06 · 语言处理

本项目没有引入 LangChain / 分词库，中文语言处理由一组自写的小工具完成，分布在 `apps/ai-service/app/services/`。

## 1. 文本分块：`text_splitter.py`

`split_text(text, size, overlap)` 纯函数：

- 先按 `\n` 切成段落/行片段（保留标题）。
- 小片段优先**拼接**进已有块（`_append_chunk`），拼不下再开新块，尽量不截断句子。
- 超过 `size` 的长段用滑窗硬切（`_hard_split`），步长 `size - overlap`，保证内容不丢。

参数来自配置：`TRIAGE_CHUNK_SIZE=500`、`TRIAGE_CHUNK_OVERLAP=80`。校验：`size>0`、`0<=overlap<size`。

## 2. 知识库加载：`kb_loader.py`

`load_kb()` 遍历 `knowledge/` 下 `*.md` / `*.txt`，逐文件 `split_text` 分块，产出 `KbChunk`：

- `id` = `{文件名}#{序号}` → 入库幂等（重跑覆盖）。
- `metadata = {"file": 文件名, "index": 序号}` → 便于溯源与展示来源。

## 3. 向量化：`embedding.py`

`EmbeddingService` 包装 `OllamaClient.embed()`（bge-m3，1024 维）：

- `embed(texts)`：批量嵌入（入库用）。
- `embed_one(text)`：单条嵌入 + 256 条 LRU 缓存（导诊查询向量可复用）。

## 4. 向量检索：`vector_store.py`

ChromaDB 持久化集合，余弦距离（`hnsw:space=cosine`）。`query()` 返回 `{document, metadata, distance}`，按相似度取 `TRIAGE_TOP_K=4` 条。接口由 `VectorStoreProtocol` 固定，便于将来换成 FAISS/SQLite。

## 5. 上下文注入与引用：`triage_service._format_context`

把检索到的片段编号后拼入 system 提示词的【医院资料】区块：

```
[1] <片段1>
[2] <片段2>
```

- 累计长度预算 `CONTEXT_BUDGET = 4000` 字符，超出截断。
- 空结果时注入「（暂无资料）」。
- 提示词要求模型回答末尾用 `[1]`、`[2]` 标注引用，前端据此展示「参考来源」。

## 6. 科室匹配：`departments.py`

`knowledge/departments.md` 是科室的单一事实来源，运行时解析为结构化 `Department` 注册表：

- `list_departments()`：全量科室（`/api/triage/departments`）。
- `match_departments(text)`：在文本里按名字查找出现的科室，按**首次出现顺序**返回（长名字优先，避免「内科」先于「心血管内科」误匹配）。
- `resolve_primary(text)`：优先解析回答中的「推荐科室：X」标记行；标记缺失 / 为「无」/ 指向不存在科室时，回退到文本中首个出现（且医院真实存在）的科室。
- 用途：导诊流结束后由后端回传 `department`（主推荐）与 `matchedDepartments`（命中列表）；前端据此渲染「挂号科室」按钮（急诊科特殊标记「前往急诊挂号」）。

## 7. 提示词设计

三个服务各自带中文 system 提示词，明确角色与约束：

| 服务 | 提示词要点 |
| --- | --- |
| Chat（`chat_service.py`） | 通用智能助手，简洁自然 |
| Companion（`companion_service.py`） | 人设「小安」，先共情再建议；不诊断不处方；急重症明确提醒就医/拨打 120 |
| Triage（`triage_service.py`） | 仅依据提供的医院资料作答、推荐科室；不诊断不处方；资料不足则建议导诊台/咨询电话；引用编号 `[1]`… |

约束（不诊断 / 不处方 / 不给出具体剂量）既是产品要求，也降低大模型在医疗场景下的风险。

## 8. 朗读文本清洗：`useSpeech.cleanTtsText`

合成语音前把回复文本清洗为可朗读的纯文本：

```ts
export function cleanTtsText(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')   // 代码块
    .replace(/`([^`]*)`/g, '$1')        // 行内代码
    .replace(/[#>*_~[\]]/g, ' ')        // Markdown 标记
    .replace(/\s+/g, ' ')
    .trim()
}
```

并按句号/问号/叹号等切句（`SENTENCE_END`）分批合成，保证「边说边读」。

## 9. 中文字符与字节处理

- SSE 序列化用 `ensure_ascii=False`，中文按原文输出。
- TTS 文本按 **UTF-8 字节**做上限截断（`_truncate_to_bytes`），避免半个字符。
- 前端 `TextDecoder({stream:true})` 处理中文跨 TCP 分片。
