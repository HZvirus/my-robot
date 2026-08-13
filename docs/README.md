# 导诊与聊天技术文档

本目录整理 `my-robot` 项目中「智能导诊（Triage）」与「聊天（Chat）」相关的实现文档，覆盖后端处理、本地模型、讯飞 TTS、前端流式与语言处理。

| 文档 | 内容 |
| --- | --- |
| [01-overview.md](./01-overview.md) | 总体架构、模块划分、配置项、SSE 事件协议、会话持久化 |
| [02-backend-processing.md](./02-backend-processing.md) | 后端处理：FastAPI 路由、服务层、流式生成、异常与取消 |
| [03-iflytek-tts.md](./03-iflytek-tts.md) | 使用讯飞：WebSocket TTS 鉴权、协议、音频流式返回 |
| [04-local-ollama.md](./04-local-ollama.md) | 使用本地模型：Ollama 的 LLM 与向量嵌入、知识库入库 |
| [05-frontend-streaming.md](./05-frontend-streaming.md) | 前端流式处理：fetch + ReadableStream 的 SSE 解析、逐字渲染、语音朗读 |
| [06-language-processing.md](./06-language-processing.md) | 语言处理：文本分块、向量化、检索、上下文拼接、科室匹配、提示词设计 |

## 相关代码位置

- 后端：`apps/ai-service/app/`
  - 路由：`api/routes/{chat,companion,triage,tts}.py`
  - 服务：`services/{chat_service,companion_service,triage_service,ollama_client,embedding,vector_store,kb_loader,text_splitter,departments,tts_service}.py`
  - DTO：`models/{chat,companion,triage,tts}.py`，ORM：`db/models.py`
- 前端：`apps/h5-app1/`（智能助手 / 智能导诊 / 挂号）、`apps/h5-app2/`（健康陪伴）
  - SSE 工具：`src/utils/sse.ts`，会话状态：`src/stores/{chat,triage,companion}.ts`
- 共享：`packages/shared-types/`（TS 类型）、`packages/ui/`（`TypewriterText`、`SpeechButton`、`useSpeech`）
- 知识库：`apps/ai-service/knowledge/*.md`，入库脚本：`apps/ai-service/scripts/ingest_kb.py`

## 能力总览

| 能力 | 路由 | 模型来源 | 是否流式 |
| --- | --- | --- | --- |
| 通用聊天（非流式，旧接口） | `POST /api/chat` | 云端 OpenAI 兼容 API（`AI_*`） | 否 |
| 通用聊天（流式，带上下文） | `POST /api/chat/stream` | 本地 Ollama | 是 |
| 健康陪伴聊天 | `POST /api/companion/chat` | 本地 Ollama | 是 |
| 智能导诊（RAG） | `POST /api/triage/chat` | 本地 Ollama + ChromaDB | 是 |
| 语音朗读（TTS） | `POST /api/tts/stream` | 讯飞 WebSocket | 是 |
