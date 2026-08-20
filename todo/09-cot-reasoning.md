# 09 · 思维链（CoT）推理

> 01 Agent 内核的深度子项。CoT（Chain-of-Thought）：让 LLM 显式输出逐步推理过程再给结论，提升复杂问题准确率、降低幻觉、推理可审计。是 07 ReAct「Thought」与 `docs/09-robot-dialog-flow.md` 中 `AgentStep.thought` 的推理内核。

## 现状对齐（基于现有代码）

- 现有四服务 SYSTEM_PROMPT 均为「直接答」指令，**无显式推理要求**：triage「请仅依据...回答」（`triage_service.py:38`）、science（`science_service.py:28`）、companion（`companion_service.py:27`）、chat（`chat_service.py:23`）。LLM 一次调用直出终答（`chat_service.py:56`）。
- LLM 调用已可透传 `temperature` / `max_tokens` / `extra`（`llm_client.py:80` `chat_stream`，`extra` 透传位 `:99`），CoT 调温与采样参数可经此注入，无需改客户端。
- triage 已有引用标注约束 `[1][2]`（`triage_service.py:44`）--CoT 推理链 + 引用可叠加为可审计证据链。
- 检索增强已就绪：triage RAG（`triage_service.py:86-89` embed + query）、science 话题向量与相似度（`science_service.py:138` `_is_new_topic`、`:39` `_cosine_similarity`），CoT 步骤可引用检索片段作推理依据、相似度可复用为 self-consistency 答案聚类。
- 持久化**只存终答**：`_persist` 双消息 user/assistant（`chat_service.py:129`、`triage_service.py:274`），不存推理过程，无法回放推理链。
- 已规划但未落地：07 ReAct 的 `react_parser.py` 解析 `Thought:`（`todo/07-react-agent.md:25`）；机器人 `AgentStep.thought` 字段（`docs/09-robot-dialog-flow.md:269`）--CoT 是其推理内核。
- **无**：CoT prompt 模板、推理链解析/抽取、self-consistency 多采样投票、推理链持久化与回放、推理质量评测。

## 目标

在现有单轮服务与未来 Agent 上叠加显式思维链：输出可解析的逐步推理 -> 结论，支持 self-consistency 提升关键决策可靠性，推理链可持久化与可审计，复用现有 LLM / SSE / 持久化基座。

## 任务

### 1. CoT 提示模板
- [ ] `app/services/agent/cot_prompt.py`：system prompt 注入「先逐步推理（包在 `<thought>...</thought>`），再给最终答案」；纯文本标记兼容本地小模型（`config.py:64` qwen2.5）
- [ ] 四服务可选启用：triage/science/companion/chat 的 SYSTEM_PROMPT 叠加 CoT 段（对齐现有 prompt 风格 `triage_service.py:38`）
- [ ] few-shot 示例库：医疗分诊 / 科普等场景的推理范例，提升小模型 CoT 稳定性

### 2. 推理链解析与分离
- [ ] `app/services/agent/cot_parser.py`：从流式 / 完整输出抽取 `<thought>` 推理链与最终答案（复用 07 `react_parser.py` 思路 `todo/07-react-agent.md:25`）
- [ ] 容错：标记缺失 / 未闭合时回退为整段答案，记录解析失败（依赖 06）

### 3. self-consistency（自洽投票）
- [ ] 对关键决策（如分诊选科）多次采样（temperature 抬高，经 `extra` 透传 `llm_client.py:99`），对结论投票取多数
- [ ] 复用 science 相似度（`science_service.py:39` `_cosine_similarity`）做答案聚类 / 去重
- [ ] 成本控制：仅高风险 / 低置信场景触发，默认关闭（依赖 06 token 预算）

### 4. 流式输出
- [ ] SSE 事件扩展：`thought`(推理链，可折叠) / `delta`(终答逐字) / `done`，沿用 `chat.py` SSE 与 `_parse_delta`（`llm_client.py:112`）
- [ ] 前端可选择性展示推理链（参考 `apps/h5-app2` 逐字渲染 + 折叠面板）

### 5. 推理链持久化与回放
- [ ] 扩展 `Message`（`models.py:43`）增 `thought` 字段，或复用 `AgentStep.thought`（`docs/09-robot-dialog-flow.md:269`），区别于只存终答的 `_persist`（`chat_service.py:129`）
- [ ] 历史回放带推理链，便于 badcase 复盘（依赖 06）

### 6. 抗幻觉与可审计
- [ ] 推理链强制引用检索片段（叠加 triage `[1][2]` 引用 `triage_service.py:44`），无依据步骤标记
- [ ] 推理与结论一致性校验：结论须由推理链支撑，不一致触发重试 / 降级

### 7. 配置
- [ ] `app/core/config.py` 增 `COT_ENABLED` / `COT_SELF_CONSISTENCY_N` / `COT_SELF_CONSISTENCY_THRESHOLD` / `COT_EMIT_THOUGHT`（对齐现有 config 风格 `config.py:96`）

## 示例执行流

```
用户: 头晕三天伴耳鸣，挂什么科？
<thought>
1. 主诉头晕 + 耳鸣
2. 检索 [1]：头晕伴耳鸣提示耳鼻喉科可能
3. 无神经系统定位体征，暂排神经内科急症
</thought>
建议挂耳鼻喉科[1]。若伴剧烈头痛/呕吐请转神经内科。
```

## 依赖

- 强依赖 01（Agent 内核 / 多步推理）；弱依赖 03（检索片段作推理依据）、06（推理质量评测 / token 成本 / 解析失败记录）、07（`Thought` 解析复用）、`docs/09-robot-dialog-flow.md`（`AgentStep.thought` 落地）。
