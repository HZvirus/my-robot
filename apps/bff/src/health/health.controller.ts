import { Controller, Get, Inject, Req } from '@nestjs/common';
import type { FastifyRequest } from 'fastify';
import { APP_CONFIG, type AppConfig } from '../config/configuration';

interface UpstreamStatus {
  url: string;
  ok: boolean;
  statusCode?: number;
  error?: string;
}

interface HealthBody {
  status: 'ok' | 'degraded';
  bff: { uptimeSeconds: number };
  upstream: UpstreamStatus;
  requestId: string;
}

const STARTED_AT = Date.now();

@Controller('health')
export class HealthController {
  constructor(@Inject(APP_CONFIG) private readonly config: AppConfig) { }

  @Get()
  async check(@Req() req: FastifyRequest): Promise<HealthBody> {
    const upstream = await probe(this.config.AI_SERVICE_URL, 2000);
    return {
      status: upstream.ok ? 'ok' : 'degraded',
      bff: { uptimeSeconds: Math.floor((Date.now() - STARTED_AT) / 1000) },
      upstream,
      requestId: req.requestId ?? '-',
    };
  }
}

async function probe(
  baseUrl: string,
  timeoutMs: number,
): Promise<UpstreamStatus> {
  const url = `${baseUrl}/health`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { signal: controller.signal });
    return {
      url: baseUrl,
      ok: resp.ok,
      statusCode: resp.status,
    };
  } catch (err) {
    return {
      url: baseUrl,
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    clearTimeout(timer);
  }
}
