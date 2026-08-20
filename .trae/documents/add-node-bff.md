# 新增 Node BFF（apps/bff）

## Context

当前 `apps/h5-app2`（Vue 3 + Vite，5174）通过 Vite 的 `server.proxy['/api'] -> http://localhost:8000` 把请求直转给 `apps/ai-service`（FastAPI，8000）。这种直连方式有几个问题：

1. **缺少边缘关注点**：没有统一的访问日志、链路 ID、错误归一化，AI 服务异常会原样透出到浏览器。
2. **凭据管理弱**：iFlytek / LLM 等服务端凭据散落在 AI 服务 `.env`，未来若加多端（H5 之外）直连 AI 服务会重复建设。
3. **多端复用难**：未来要接小程序、第三方调用方时，每个新前端都要重做代理/鉴权/日志。

为此新增一个 Node BFF（`apps/bff`，NestJS 11 + Fastify adapter），专门负责：
- 透传 `/api/*` HTTP（含 SSE）和 `/api/smart-tts/ws` WebSocket
- 访问日志（method / path / status / latency / X-Request-Id）
- 凭据脱敏（Authorization / ?token 永不进日志）
- 错误归一化（统一 `{code, message, requestId}` 响应体，upstream 不可达返回 502）

初始阶段不引入：限流、缓存、响应聚合、鉴权改造、自身持有的服务端凭据。BFF 是「带可观测性的纯透传层」，AI 服务仍持有所有业务凭据与状态。

## 架构与数据流

```
H5 (5174)  --/api/*-->  BFF (5175)  --/api/*-->  AI service (8000)
  Vite proxy              NestJS                  FastAPI
                          (Fastify adapter)       (持有 iFlytek/LLM/DB)
  - 浏览器保持原样
  - 仅改 vite.config.ts
                              ├── /api/* (HTTP+SSE) : 透传 fetch + pipe
                              └── /api/smart-tts/ws : 双向 WS 桥接
```

## 文件改动清单

### 新增（`apps/bff/`）

- `apps/bff/package.json` — 名称 `@my-robot/bff`，`type: module`，脚本 `dev: tsx watch src/main.ts` / `build: tsc -p tsconfig.json` / `start: node dist/main.js` / `lint / typecheck / clean`
- `apps/bff/tsconfig.json` — extends `../../tsconfig.base.json`，`outDir: dist`，`rootDir: src`
- `apps/bff/.env.example` — `BFF_PORT=5175`、`AI_SERVICE_URL=http://localhost:8000`、`LOG_LEVEL=info`、`CORS_ORIGINS=["http://localhost:5173","http://localhost:5174"]`
- `apps/bff/README.md` — 启动方式、端口、环境变量、与 AI 服务的依赖关系
- `apps/bff/src/main.ts` — `NestFactory.create(AppModule, new FastifyAdapter())`，监听 `${BFF_PORT}`，挂 `app.enableShutdownHooks()`
- `apps/bff/src/app.module.ts` — 组合 Config / Health / Proxy / Ws / Common 模块
- `apps/bff/src/config/configuration.ts` — 用 `zod` 解析 env，导出 `ConfigService`
- `apps/bff/src/common/middleware/request-id.middleware.ts` — 读 `X-Request-Id` 或生成 `crypto.randomUUID()`，挂到 `req.requestId`（Fastify decorator）
- `apps/bff/src/common/interceptors/logging.interceptor.ts` — 在 `intercept(ctx, next)` 中：用 `performance.now()` 量请求耗时，结束时 `Logger.log(\`${method} ${url} ${status} ${latencyMs}ms reqId=${reqId}\`)`。Pino/NestJS Logger 都已自带 redact 能力；额外手动确认 `Authorization` / `?token=` 不出现在日志字符串中
- `apps/bff/src/common/filters/all-exceptions.filter.ts` — 捕获所有未处理异常：HTTP 异常透传 status；fetch 抛 `ECONNREFUSED` / 超时 → 502 `{code:"upstream_unavailable", message, requestId}`；其它 500 `{code:"internal_error", message, requestId}`
- `apps/bff/src/health/health.controller.ts` — `GET /health` → `{status:"ok", upstream: await probe(AI_SERVICE_URL+'/health', 2000)}`；upstream 字段返回 `{url, ok, statusCode?}`
- `apps/bff/src/proxy/proxy.controller.ts` — `@All('/api/*')`（捕获 `/api/(.*)` 路径），用 `@Req() req: FastifyRequest` + `@Res({passthrough:false}) res: FastifyReply`。逻辑：
  1. 构造 upstreamUrl = `${AI_SERVICE_URL}${req.url}`（保留 query string）
  2. 过滤请求头：删除 `host`、`content-length`；保留 `authorization` / `content-type` / `accept` / `x-conversation-id` 等
  3. `fetch(upstreamUrl, {method, headers, body: req.raw, duplex:'half'})`（Fastify 的 `req.raw` 是 Node IncomingMessage，可作 Readable）
  4. 拿到 `upstreamResp`：删 `content-length`、`content-encoding`，注入 `x-accel-buffering: no` 与 `cache-control: no-cache, no-transform`
  5. `res.raw.writeHead(upstreamResp.status, headers); Readable.fromWeb(upstreamResp.body).pipe(res.raw)`
  6. 监听 `req.raw` 的 `close` / `aborted` 事件以中断 upstream fetch
- `apps/bff/src/proxy/proxy.module.ts` — 提供 `AI_SERVICE_URL` token
- `apps/bff/src/ws/smart-tts.gateway.ts` — `@WebSocketGateway({ path: '/api/smart-tts/ws' })`，`handleConnection(client, request)`：
  1. 从 `request.query.token` 取 device token
  2. `new WebSocket(\`${AI_SERVICE_URL_WS}/api/smart-tts/ws?token=${encodeURIComponent(token)}\`, {perMessageDeflate: false})`（用 `ws` 包，iFlytek 不支持 permessage-deflate）
  3. `upstream.on('message', m => client.send(m))` / `client.on('message', m => upstream.send(m))`
  4. 任一侧 `close` / `error` → 关闭另一侧；30s 空闲超时
- `apps/bff/src/ws/ws.module.ts`

### 依赖（apps/bff/package.json）

- runtime: `@nestjs/core@^11`、`@nestjs/common@^11`、`@nestjs/platform-fastify@^11`、`@nestjs/websockets@^11`、`@fastify/cors@^10`、`ws@^8`、`zod@^3`
- dev: `typescript@^5.4`、`tsx@^4`、`@types/node@^22`、`@types/ws@^8`

### 改动（最小化）

- `apps/h5-app2/vite.config.ts` — 仅把 `proxy['/api'].target` 由 `'http://localhost:8000'` 改为 `'http://localhost:5175'`，保留 `changeOrigin: true, ws: true`
- `README.md`（项目根）— 在 Structure 段加 `apps/bff/` 一行
- `pnpm-workspace.yaml` — 已是 glob `apps/*`，自动包含新包，**无需改**
- `turbo.json` — 已有 `dev: { cache: false, persistent: true }`，**无需改**；`pnpm dev` 顶层会自动并行启动 bff

## 关键实现细节

1. **SSE 字节级透传**：用 Node 20+ 原生 `fetch` + `Readable.fromWeb`；禁止任何框架层 buffer。`replyInterceptor` 思路不必要——controller 自己就是 `passthrough: false`，直接接管 `res.raw`。
2. **超时**：upstream fetch 5s connect timeout；SSE/WS 一旦建连不设读超时（让流自然走完）。`AbortController` 在客户端断开时取消。
3. **凭据脱敏**：NestJS Logger 默认不打印 header；额外在 LoggingInterceptor 内显式 `delete headersCopy.authorization` 后再决定是否记 debug 日志；Pino redact 配置（如果切换到 Pino 风格）作为长期建议。
4. **健康探针**：BFF 启动时单次 GET `${AI_SERVICE_URL}/health`，2s timeout；失败仅 `Logger.warn`，不抛错。`/health` 端点每次都做一次轻探针，便于 K8s readiness 区分「BFF 活但上游挂」与「BFF 挂」。
5. **优雅停机**：`app.enableShutdownHooks()` + Fastify adapter 默认会清理 keep-alive 连接；WS gateway 在 `handleDisconnect` 内关闭 upstream。
6. **错误归一化**：所有响应（含 SSE 错误帧）走统一形状，但 SSE 流内仍由 AI 服务产出 `data: {"error":...}` 帧——BFF 不在流内改写帧内容，只在外层 HTTP 错误（如 502、504）时返回归一化 JSON。

## 验证

1. **构建/类型/单测**
   - `pnpm install`（workspace 自动链接新包）
   - `pnpm -F @my-robot/bff typecheck` 通过
   - `pnpm -F @my-robot/bff build` 通过
2. **本地联调**
   - 启动 AI 服务：`cd apps/ai-service && .venv\Scripts\activate && uvicorn app.main:app --port 8000`
   - 启动 BFF：`pnpm -F @my-robot/bff dev`（应监听 5175）
   - 启动前端：`pnpm -F @my-robot/h5-app2 dev`
   - 浏览器打开 `http://localhost:5174/companion`，发送消息，验证：
     - 助手回复仍逐字渲染
     - BFF 控制台看到一条 `POST /api/companion/chat 200 <ms>ms reqId=<uuid>` 日志
     - 浏览器 Network 中该请求 `Transfer-Encoding: chunked`、无 `Content-Length`
3. **WS 桥接**
   - 进入 `/companion/smart` 或 `/companion/fast` 触发超拟人 TTS
   - BFF 日志显示 `WS /api/smart-tts/ws connected → upstream connected` 与对应关闭
   - 浏览器 Network WS 帧双向均能看到
4. **upstream 不可用**
   - 停掉 AI 服务，再发请求：浏览器收到 502 响应体 `{code:"upstream_unavailable", message, requestId}`
   - BFF 日志级别 warn，无未捕获栈
5. **凭据脱敏**
   - 故意用错误 token 发请求，触发 401；查看 BFF 日志确认无 token 字符串明文出现
6. **回归**
   - `pnpm dev`（根目录 turbo）三端同启：h5-app2 + bff + ai-service 全部 ready

## 后续可扩展（不在本任务范围）

- Pino + pino-pretty 替换 NestJS Logger
- `/metrics` Prometheus 端点
- 限流（fastify-rate-limit）
- 响应聚合（dashboard 端点）
- BFF 自身持有 iFlytek 签发能力，把 `ws-url` 也下沉到 BFF
