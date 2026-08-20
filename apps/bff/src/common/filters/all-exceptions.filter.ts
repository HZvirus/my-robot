import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { FastifyRequest, FastifyReply } from 'fastify';

interface ErrorBody {
  code: string;
  message: string;
  requestId: string;
}

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger('Exception');

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const req = ctx.getRequest<FastifyRequest>();
    const res = ctx.getResponse<FastifyReply>();
    const requestId = req.requestId ?? '-';

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let code = 'internal_error';
    let message: string =
      exception instanceof Error ? exception.message : 'unknown error';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const resp = exception.getResponse();
      if (typeof resp === 'string') {
        message = resp;
      } else if (resp && typeof resp === 'object') {
        const r = resp as { message?: unknown; code?: unknown };
        if (typeof r.message === 'string') message = r.message;
        else if (Array.isArray(r.message))
          message = (r.message as unknown[]).map(String).join('; ');
        if (typeof r.code === 'string') code = r.code;
      }
      if (status >= 500) {
        code = 'upstream_error';
      } else {
        code = mapStatusToCode(status);
      }
    } else if (isUpstreamUnavailable(exception)) {
      status = HttpStatus.BAD_GATEWAY;
      code = 'upstream_unavailable';
      message = 'upstream service unavailable';
    }

    const body: ErrorBody = { code, message, requestId };
    this.logger.warn(
      `reqId=${requestId} ${status} ${code}: ${truncate(message, 200)}`,
    );

    this.safeSend(res, status, body, requestId);
  }

  private safeSend(
    res: FastifyReply,
    status: number,
    body: ErrorBody,
    requestId: string,
  ): void {
    try {
      if (res.sent || res.raw.writableEnded || res.raw.headersSent) {
        return;
      }
      if (typeof res.status === 'function' && typeof res.send === 'function') {
        res.status(status).send(body);
        return;
      }
      const raw = res.raw;
      if (raw && !raw.headersSent) {
        raw.statusCode = status;
        raw.setHeader('Content-Type', 'application/json; charset=utf-8');
        raw.end(JSON.stringify(body));
      }
    } catch (err) {
      this.logger.error(
        `failed to write error response reqId=${requestId}: ${(err as Error).message}`,
      );
    }
  }
}

function mapStatusToCode(status: number): string {
  switch (status) {
    case 400:
      return 'bad_request';
    case 401:
      return 'unauthorized';
    case 403:
      return 'forbidden';
    case 404:
      return 'not_found';
    case 409:
      return 'conflict';
    case 413:
      return 'payload_too_large';
    case 415:
      return 'unsupported_media_type';
    case 429:
      return 'rate_limited';
    default:
      return status >= 500 ? 'upstream_error' : 'http_error';
  }
}

function isUpstreamUnavailable(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const name = err.name ?? '';
  if (name === 'FetchError' || name === 'AbortError') return true;
  const code = (err as NodeJS.ErrnoException).code;
  if (
    code === 'ECONNREFUSED' ||
    code === 'ECONNRESET' ||
    code === 'ENOTFOUND' ||
    code === 'ETIMEDOUT' ||
    code === 'EAI_AGAIN' ||
    code === 'UND_ERR_SOCKET' ||
    code === 'UND_ERR_CONNECT_TIMEOUT'
  ) {
    return true;
  }
  return false;
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n)}...` : s;
}
