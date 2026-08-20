# BFF (Backend for Frontend)

Node 透传层，介于 H5 前端与 `apps/ai-service` (Python FastAPI) 之间，端口 `5175`。

## 职责

- 透传 `/api/*` HTTP 请求（含 SSE 流式）
- 透传 `/api/smart-tts/ws` WebSocket（双向桥接讯飞超拟人 TTS）
- 访问日志（method / path / status / latency / `X-Request-Id`）
- 凭据脱敏（`Authorization` 与 `?token=` 永不进日志）
- 错误归一化：`{code, message, requestId}`，upstream 不可达返回 502

**不做**：鉴权改造、限流、缓存、响应聚合。所有业务凭据（iFlytek / LLM / DB）仍由 AI 服务持有。

## 启动

```bash
# 根目录
pnpm install
pnpm dev          # 同时拉起 h5-app2(5174) + bff(5175) + ai-service(8000)

# 单独启动
pnpm -F @my-robot/bff dev
```

启动时 BFF 会向 `${AI_SERVICE_URL}/health` 发起一次 2s 探针，失败仅 warn 不退出。

## 环境变量（`.env`）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `BFF_PORT` | `5175` | 监听端口 |
| `BFF_HOST` | `0.0.0.0` | 监听地址 |
| `AI_SERVICE_URL` | `http://localhost:8000` | 上游 AI 服务 |
| `LOG_LEVEL` | `info` | NestJS Logger 级别 |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:5174"]` | JSON 数组 |

## 端点

- `GET /health` → `{status, upstream: {url, ok, statusCode?}}`
- `ALL /*` → 透传到 `AI_SERVICE_URL`（捕获 `/api/*`，SSE 字节级转发）
- `WS /api/smart-tts/ws?token=<device_token>` → 双向桥接上游同名端点

## 联调验证

```bash
# 健康
curl http://localhost:5175/health

# 透传 + 日志（应看到 POST /api/.../chat 200 <ms>ms reqId=<uuid>）
curl -N -X POST http://localhost:5175/api/companion/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{"message":"你好"}'
```
