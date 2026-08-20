# 06 · 可观测性体系建设与数据驱动闭环（核心加分项）

> JD 对应：自动化评测与可观测体系（Trace / Token 消耗 / 耗时 / 工具成功率）；Badcase 多维分析；离线回放；Prompt 版本管理与自动化评测，杜绝盲盒式迭代。

## 现状对齐（基于现有代码）

- **日志**：`app/core/logger.py`，结构化有限。
- **Prompt 硬编码**：常量散落各服务（`chat_service.py:23` `SYSTEM_PROMPT`、`triage_service.py:38`、`science_service.py:28`），无版本管理。
- **无** trace、无 token 计数、无指标、无 badcase 分析、无离线回放、无评测集。
- 已有的可复用锚点：会话/消息可定位执行流（`Conversation`/`Message`）、science 已有相似度日志（`science_service.py:145`），可扩展为指标。

## 目标

建设 Trace + 指标 + 评测 + 回放 + Prompt 版本的闭环，使每次 Prompt/模型/参数变更都能量化验证，杜绝「改好一个坏掉一批」。

## 任务

### 1. Tracing
- [ ] `app/core/observability/trace.py`：每次 Agent 执行生成 trace（span：检索 / LLM / 工具 / 持久化），串联 conv_id + step
- [ ] 结构化日志关联 trace_id（扩展 `logger.py`）

### 2. 指标采集
- [ ] Token 消耗（prompt/completion）、各阶段耗时、工具成功率、检索召回数/分数
- [ ] 指标存储：复用 SQLite 增 `Metric` 表 或 Prometheus

### 3. Badcase 多维分析
- [ ] 线上问题样本采集与标注；按维度分类归因（检索缺失 / 幻觉 / 工具失败 / 超时）

### 4. 离线回放
- [ ] `replay.py`：录制请求 + 上下文 + 模型版本 + prompt 版本，离线精确复现执行流（依赖 trace + prompt 版本）

### 5. Prompt 版本管理
- [ ] `app/core/prompts/`：提示词外置为带版本文件/DB，替换硬编码常量
- [ ] 版本绑定 trace，变更可追溯

### 6. 自动化评测
- [ ] `app/eval/` + `tests/`：评测集（导诊 / SQL / 工具用例），指标（召回率 / 准确率 / 幻觉率 / 工具成功率）
- [ ] CI 跑评测，变更前后对比（依赖 03 调参 + 01 Agent）

## 依赖

- 横向贯穿 01（步骤 trace）、03（召回指标）、04（工具成功率）、05（Token/耗时）；是其他模块调参与迭代的验收依据。
