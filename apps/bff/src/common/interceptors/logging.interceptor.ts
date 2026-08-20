import {
  CallHandler,
  ExecutionContext,
  Injectable,
  Logger,
  NestInterceptor,
} from '@nestjs/common';
import { Observable, tap } from 'rxjs';
import type { FastifyRequest, FastifyReply } from 'fastify';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  private readonly logger = new Logger('HTTP');

  intercept(ctx: ExecutionContext, next: CallHandler): Observable<unknown> {
    if (ctx.getType() !== 'http') {
      return next.handle();
    }
    const http = ctx.switchToHttp();
    const req = http.getRequest<FastifyRequest>();
    const res = http.getResponse<FastifyReply>();
    const startedAt = performance.now();
    const requestId = req.requestId ?? '-';
    const method = req.method;
    const path = req.url;

    return next.handle().pipe(
      tap({
        next: () => this.log(method, path, res.statusCode, startedAt, requestId),
        error: () =>
          this.log(method, path, res.statusCode, startedAt, requestId, 'error'),
      }),
    );
  }

  private log(
    method: string,
    path: string,
    status: number,
    startedAt: number,
    requestId: string,
    suffix = 'ok',
  ): void {
    const ms = (performance.now() - startedAt).toFixed(1);
    const line = `${method} ${path} ${status} ${ms}ms reqId=${requestId}`;
    if (suffix === 'error') {
      this.logger.warn(line);
    } else {
      this.logger.log(line);
    }
  }
}
