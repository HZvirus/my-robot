import {
  All,
  Controller,
  Inject,
  Logger,
  Req,
  Res,
} from '@nestjs/common';
import { Readable } from 'node:stream';
import type { FastifyRequest, FastifyReply } from 'fastify';
import { APP_CONFIG, type AppConfig } from '../config/configuration';
import { forwardHttp } from './upstream';

@Controller()
export class ProxyController {
  private readonly logger = new Logger('Proxy');

  constructor(@Inject(APP_CONFIG) private readonly config: AppConfig) { }

  @All('/*')
  async proxy(
    @Req() req: FastifyRequest,
    @Res() res: FastifyReply,
  ): Promise<void> {
    const requestId = req.requestId ?? '-';
    const headers = req.headers as Record<string, string | string[] | undefined>;
    const rawReq = req.raw;
    const method = (rawReq.method ?? 'GET').toUpperCase();
    const hasBody = !['GET', 'HEAD'].includes(method);

    let bodyStream: Readable | Buffer | Uint8Array | null = null;
    if (hasBody && req.body != null) {
      if (Buffer.isBuffer(req.body)) {
        bodyStream = req.body;
      } else if (typeof req.body === 'string') {
        bodyStream = Buffer.from(req.body, 'utf8');
      } else {
        bodyStream = Buffer.from(JSON.stringify(req.body), 'utf8');
      }
    }

    res.hijack();
    const rawRes = res.raw;

    try {
      const forward = await forwardHttp({
        baseUrl: this.config.AI_SERVICE_URL,
        method,
        path: req.url,
        headers,
        bodyStream,
        connectTimeoutMs: this.config.AI_SERVICE_TIMEOUT,
        requestId,
      });

      rawRes.writeHead(forward.status, forward.headers);

      if (!forward.body) {
        rawRes.end();
        return;
      }

      const cleanup = () => {
        forward.abort();
        if (!rawRes.writableEnded) {
          rawRes.end();
        }
      };

      forward.body.on('error', (err) => {
        this.logger.warn(
          `upstream stream error reqId=${requestId}: ${err.message}`,
        );
        cleanup();
      });
      rawReq.on('close', cleanup);
      rawReq.on('aborted', cleanup);
      rawRes.on('close', cleanup);

      forward.body.pipe(rawRes);
    } catch (err) {
      this.logger.error(
        `proxy handler error reqId=${requestId}: ${(err as Error).message}`,
      );
      if (!rawRes.headersSent && !rawRes.writableEnded) {
        rawRes.statusCode = 502;
        rawRes.setHeader('Content-Type', 'application/json; charset=utf-8');
        rawRes.end(
          JSON.stringify({
            code: 'upstream_unavailable',
            message: 'upstream service unavailable',
            requestId,
          }),
        );
      }
    }
  }
}
