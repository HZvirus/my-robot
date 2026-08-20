import { Logger } from '@nestjs/common';
import type { WebSocket as WsClient } from 'ws';
import WebSocket from 'ws';

const IDLE_TIMEOUT_MS = 30_000;

const logger = new Logger('WsRelay');

export interface RelayContext {
  aiServiceWsUrl: string;
}

export function handleSmartTtsWs(
  client: WsClient,
  request: { query: Record<string, unknown> },
  ctx: RelayContext,
): void {
  const token = readToken(request.query);
  const requestId =
    typeof request.query.requestId === 'string'
      ? request.query.requestId
      : '-';

  const upstreamUrl = token
    ? `${ctx.aiServiceWsUrl}/api/smart-tts/ws?token=${encodeURIComponent(token)}`
    : `${ctx.aiServiceWsUrl}/api/smart-tts/ws`;

  logger.log(`client connected → dialing upstream reqId=${requestId}`);

  const upstream = new WebSocket(upstreamUrl, { perMessageDeflate: false });
  let closed = false;

  const closeBoth = (reason: string, code?: number) => {
    if (closed) return;
    closed = true;
    logger.log(
      `closing relay reqId=${requestId} reason=${reason}${
        code !== undefined ? ` code=${code}` : ''
      }`,
    );
    try {
      if (upstream.readyState === WebSocket.OPEN) upstream.close(1011, reason);
      else if (upstream.readyState === WebSocket.CONNECTING) upstream.terminate();
    } catch {
      /* ignore */
    }
    try {
      if (client.readyState === client.OPEN) client.close(1011, reason);
      else if (client.readyState === client.CONNECTING) client.terminate();
    } catch {
      /* ignore */
    }
  };

  let idleTimer: NodeJS.Timeout | null = null;
  const resetIdle = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => closeBoth('idle timeout'), IDLE_TIMEOUT_MS);
  };
  resetIdle();

  upstream.on('open', () => {
    logger.log(`upstream connected reqId=${requestId}`);
  });

  upstream.on('message', (data, isBinary) => {
    resetIdle();
    if (client.readyState === client.OPEN) {
      client.send(data, { binary: isBinary });
    }
  });

  client.on('message', (data, isBinary) => {
    resetIdle();
    if (upstream.readyState === WebSocket.OPEN) {
      upstream.send(data, { binary: isBinary });
    }
  });

  upstream.on('error', (err) => {
    logger.warn(`upstream ws error reqId=${requestId}: ${err.message}`);
    closeBoth('upstream error');
  });

  client.on('error', (err: Error) => {
    logger.warn(`client ws error reqId=${requestId}: ${err.message}`);
    closeBoth('client error');
  });

  upstream.on('close', (code, reason) => {
    closeBoth(`upstream closed (${code})`);
    void reason;
  });

  client.on('close', (code) => {
    closeBoth(`client closed (${code})`);
  });
}

function readToken(q: Record<string, unknown>): string | undefined {
  const v = q.token;
  return typeof v === 'string' && v.length > 0 ? v : undefined;
}
