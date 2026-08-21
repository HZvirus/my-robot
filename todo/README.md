# my-robot · AI 能力建设代办清单

依据「智能体工程师」JD 六大能力域，逐模块拆解代办，并对齐到 `apps/ai-service` 现有代码。每个文件含「现状对齐（带 file:line 证据）+ 目标 + 任务清单 + 依赖」。

| 模块 | 代办文件 | JD 关键词 |
| --- | --- | --- |
| 01 | [01-agent-core.md](./01-agent-core.md) | Planning、多步推理、Function Calling、多轮状态管理 |
| 02 | [02-memory-user-profile.md](./02-memory-user-profile.md) | 长短期记忆、上下文压缩、记忆抽取、遗忘、用户画像、情绪理解 |
| 03 | [03-rag-pipeline.md](./03-rag-pipeline.md) | 切分、Embedding、混合检索、Rerank、Query Rewrite、抗幻觉 |
| 04 | [04-tool-skills.md](./04-tool-skills.md) | 工具集、交互契约与错误语义、Skill 沉淀、按需加载、跨业务复用 |
| 05 | [05-workflow-orchestration.md](./05-workflow-orchestration.md) | ReAct/Plan-and-Execute/多 Agent、SSE、中断恢复、上下文剪裁、Token 成本 |
| 06 | [06-observability-eval.md](./06-observability-eval.md) | Trace/Token/耗时/工具成功率、Badcase、离线回放、Prompt 版本、自动评测 |

## 落地子项

- [text-to-sql.md](./text-to-sql.md) —— 首个落地工具（归属 04 工具生态），复用 `llm_client` 查询现有 `User/Conversation/Message`。
- [07-react-agent.md](./07-react-agent.md) -- ReAct Agent 深度落地（05 子项）：Thought/Action/Observation 循环、解析器、步骤持久化与中断恢复、流式 SSE 事件。
- [08-multi-agent.md](./08-multi-agent.md) -- 多 Agent 协作深度落地（05 子项）：supervisor/router 统一入口、handoff 移交、并行/串行编排、共享上下文与防循环。
- [09-cot-reasoning.md](./09-cot-reasoning.md) -- 思维链（CoT）深度落地（01 子项）：显式逐步推理、推理链解析与持久化、self-consistency 投票、抗幻觉可审计。
- [10-dialog-fsm.md](./10-dialog-fsm.md) -- 对话状态机深度落地（01 子项）：FSM 引擎、状态/转移/守卫、状态快照中断恢复、跨阶段记忆，承载 docs/09 导诊全流程。
- [11-agent-review-fixes.md](./11-agent-review-fixes.md) -- 现有 ReAct Agent 实现（`app/services/agent/`）代码走查修复清单：上下文过滤/竞态/脱管 ORM、主循环异常兜底、工具注册扩展、注入通道、测试补齐。

## 依赖关系

```
06 可观测/评测  ──贯穿验收──>  所有模块
01 Agent 内核  ──调用──>  04 工具生态
01/04          ──编排──>  05 工作流(ReAct/Plan-Execute/多Agent)
07 ReAct        ──子项──>  05 单 Agent 循环
08 多Agent      ──子项──>  05 多 Agent 协作(依赖 01 收敛 + 04 工具)
09 CoT          ──子项──>  01 多步推理(ReAct Thought / AgentStep.thought 内核)
10 FSM          ──子项──>  01 多轮状态管理(承载 docs/09 导诊全流程)
02 记忆/画像    ──剪裁──>  05 上下文剪裁
03 RAG         ──召回──>  01/05 检索增强
text-to-sql    ──沉淀为──> 04 首个工具
```

## 建议推进顺序

1. 06 先行打底（trace + 指标），为后续迭代提供验收基线
2. 03 RAG 全链路（提升现有导诊召回/抗幻觉，收益快）
3. 04 工具生态 + text-to-sql 落地（沉淀首个工具）
4. 01 Agent 内核（接入工具，从单轮走向多步）
5. 02 记忆与画像（个性化）
6. 05 工作流编排（多步/多 Agent、中断恢复、性能）
