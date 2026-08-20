# 02 · 记忆与用户画像系统

> JD 对应：长短期记忆机制 —— 对话历史管理、上下文压缩、记忆抽取、遗忘策略；用户画像与情绪理解；个性化推荐与长期用户状态维护。

## 现状对齐（基于现有代码）

- **短期记忆**：各服务 `_load_history` 取最近 N 条线性拼入（`config.py:20` `CHAT_MAX_HISTORY=10`、`config.py:85` `TRIAGE_MAX_HISTORY=6`、`config.py:23/26` companion/science=12）。无压缩，仅截断。
- **遗忘雏形**：`science_service` 话题漂移检测 —— 加权话题质心 + 余弦相似度，低于阈值（`config.py:29` `SCIENCE_TOPIC_SIM_THRESHOLD=0.51`）即新开会话（`science_service.py:114` `_load_topic_vector`、`:138` `_is_new_topic`）。但仅 science 用，且是「切会话」而非「压缩记忆」。
- **无长期记忆、无记忆抽取、无上下文压缩、无用户画像**（`User` 仅 id/token_hash/role，`models.py:17`）、无情绪理解、无个性化。

## 目标

构建分层记忆（短期原文 + 长期结构化），实现压缩 / 抽取 / 遗忘，沉淀用户画像与情绪状态，支撑个性化与长期维护。

## 任务

### 1. 长短期记忆
- [ ] 新建 `app/services/memory/` 包：`memory_store.py`
- [ ] 长期记忆表：`app/db/models.py` 增加 `Memory`（user_id、kind=episode/summary、content、embedding、importance、last_used、created_at）
- [ ] 记忆抽取：每轮后异步抽取关键事实/偏好写入长期记忆（LLM 抽取）
- [ ] 检索式召回：用 embedding 召回相关长期记忆注入上下文（复用 `embedding.py`、`vector_store.py`）

### 2. 上下文压缩
- [ ] `context_compressor.py`：超阈值时对早期历史做 LLM 摘要压缩，替代当前粗暴截断
- [ ] 分级保留：最近 N 条原文 + 更早的摘要

### 3. 遗忘策略
- [ ] 基于重要度 + 时间 + 使用频率的衰减/淘汰；泛化 science 话题漂移思路到通用记忆

### 4. 用户画像
- [ ] `app/db/models.py` 增加 `UserProfile`（user_id、attributes JSON、updated_at）
- [ ] 画像抽取与更新（从对话中提取偏好/特征），注入 system prompt

### 5. 情绪理解
- [ ] 情绪识别（规则 / 小模型 / LLM 标注），写入记忆与画像
- [ ] 影响 TTS 语气（与 `smart_tts_service.py` 联动）

### 6. 个性化推荐
- [ ] 基于画像/记忆的推荐召回（导诊科室、科普内容等）

## 依赖

- 复用 `embedding.py` / `vector_store.py`；与 05（上下文剪裁）、06（trace 记录记忆操作）联动。
