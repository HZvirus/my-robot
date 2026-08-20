import { Readable } from 'node:stream';

const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

const RESPONSE_HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'content-length',
  'content-encoding',
]);

export interface ForwardResult {
  status: number;
  headers: Record<string, string>;
  body: Readable | null;
  abort: () => void;
}

export interface ForwardOptions {
  baseUrl: string;
  method: string;
  path: string;
  headers: Record<string, string | string[] | undefined>;
  bodyStream: Readable | Buffer | Uint8Array | null;
  connectTimeoutMs: number;
  requestId: string;
}

export async function forwardHttp(
  opts: ForwardOptions,
): Promise<ForwardResult> {
  const url = joinUrl(opts.baseUrl, opts.path);
  const forwardHeaders = filterRequestHeaders(opts.headers);
  forwardHeaders['x-forwarded-host'] = new URL(url).host;
  forwardHeaders['x-forwarded-proto'] = new URL(url).protocol.replace(':', '');
  forwardHeaders['x-request-id'] = opts.requestId;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.connectTimeoutMs);

  const init: RequestInit = {
    method: opts.method,
    headers: forwardHeaders,
    signal: controller.signal,
  };
  if (opts.bodyStream && !['GET', 'HEAD'].includes(opts.method.toUpperCase())) {
    if (Buffer.isBuffer(opts.bodyStream)) {
      init.body = opts.bodyStream;
    } else {
      (init as RequestInit & { duplex: 'half' }).duplex = 'half';
      init.body = opts.bodyStream as unknown as RequestInit['body'];
    }
  }

  const resp = await fetch(url, init);
  clearTimeout(timer);

  const respHeaders = filterResponseHeaders(resp.headers);
  ensureStreamingHeaders(respHeaders, resp.headers.get('content-type'));

  let body: Readable | null = null;
  if (resp.body) {
    body = Readable.fromWeb(resp.body as unknown as import('stream/web').ReadableStream);
  }

  return {
    status: resp.status,
    headers: respHeaders,
    body,
    abort: () => {
      controller.abort();
      body?.destroy();
    },
  };
}

function filterRequestHeaders(
  src: Record<string, string | string[] | undefined>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(src)) {
    if (v === undefined) continue;
    const lower = k.toLowerCase();
    if (HOP_BY_HOP.has(lower)) continue;
    if (Array.isArray(v)) {
      out[lower] = v.join(', ');
    } else {
      out[lower] = v;
    }
  }
  return out;
}

function filterResponseHeaders(src: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  src.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (RESPONSE_HOP_BY_HOP.has(lower)) return;
    out[lower] = value;
  });
  return out;
}

function ensureStreamingHeaders(
  out: Record<string, string>,
  contentType: string | null,
): void {
  if (contentType && contentType.toLowerCase().includes('text/event-stream')) {
    out['cache-control'] = 'no-cache, no-transform';
    out['x-accel-buffering'] = 'no';
  } else {
    out['cache-control'] = out['cache-control'] ?? 'no-cache';
  }
  out['x-accel-buffering'] = out['x-accel-buffering'] ?? 'no';
}

function joinUrl(base: string, path: string): string {
  const trimmedBase = base.replace(/\/+$/, '');
  const trimmedPath = path.startsWith('/') ? path : `/${path}`;
  return `${trimmedBase}${trimmedPath}`;
}
