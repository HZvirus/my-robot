import 'dotenv/config';

import { randomUUID } from 'node:crypto';
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { NestFastifyApplication, FastifyAdapter } from '@nestjs/platform-fastify';
import websocket from '@fastify/websocket';
import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';

import { AppModule } from './app.module';
import { APP_CONFIG } from './config/configuration';
import { WsRegistrar } from './ws/ws.registrar';

const REQUEST_ID_HEADER = 'x-request-id';

const logger = new Logger('Bootstrap');

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter({
      logger: false,
      bodyLimit: 10 * 1024 * 1024,
    }),
  );

  const config = app.get(APP_CONFIG);
  const fastify = app.getHttpAdapter().getInstance() as FastifyInstance;

  registerRequestId(fastify);
  registerCors(fastify, config.CORS_ORIGINS);
  fastify.removeAllContentTypeParsers();
  fastify.addContentTypeParser('*', { parseAs: 'buffer' }, (_req, body, done) => {
    done(null, body);
  });
  await fastify.register(websocket);

  app.enableShutdownHooks();

  await probeUpstream(config.AI_SERVICE_URL);

  const wsRegistrar = app.get(WsRegistrar);
  wsRegistrar.register(fastify);

  await app.listen({ port: config.BFF_PORT, host: config.BFF_HOST });

  logger.log(`BFF listening on http://${config.BFF_HOST}:${config.BFF_PORT}`);
  logger.log(`upstream ${config.AI_SERVICE_URL}`);
}

function registerRequestId(fastify: FastifyInstance): void {
  fastify.addHook('onRequest', (req: FastifyRequest, reply: FastifyReply, done) => {
    const incoming = req.headers[REQUEST_ID_HEADER];
    const id =
      typeof incoming === 'string' && incoming.length > 0
        ? incoming
        : randomUUID();
    req.requestId = id;
    reply.header(REQUEST_ID_HEADER, id);
    done();
  });
}

function registerCors(
  fastify: FastifyInstance,
  allowedOrigins: readonly string[],
): void {
  const allowAll = allowedOrigins.includes('*');
  fastify.addHook('onRequest', (req, reply, done) => {
    const origin = req.headers.origin;
    if (origin && (allowAll || allowedOrigins.includes(origin))) {
      reply.header('Access-Control-Allow-Origin', origin);
      reply.header('Vary', 'Origin');
      reply.header('Access-Control-Allow-Credentials', 'true');
    }
    if (req.method === 'OPTIONS') {
      reply.header(
        'Access-Control-Allow-Methods',
        'GET,POST,PUT,PATCH,DELETE,OPTIONS',
      );
      reply.header(
        'Access-Control-Allow-Headers',
        (req.headers['access-control-request-headers'] as string) ??
        'Content-Type, Authorization, X-Conversation-Id, X-Request-Id',
      );
      reply.status(204).send();
      return;
    }
    done();
  });
}

async function probeUpstream(baseUrl: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2000);
  try {
    const resp = await fetch(`${baseUrl}/health`, { signal: controller.signal });
    if (resp.ok) {
      logger.log(`upstream reachable (${resp.status})`);
    } else {
      logger.warn(`upstream returned ${resp.status}; continuing anyway`);
    }
  } catch (err) {
    logger.warn(
      `upstream not reachable (${(err as Error).message}); continuing anyway`,
    );
  } finally {
    clearTimeout(timer);
  }
}

bootstrap().catch((err) => {
  // eslint-disable-next-line no-console
  console.error('BOOT FAILED:', err);
  logger.error(`failed to start BFF: ${(err as Error).message}`);
  process.exit(1);
});
