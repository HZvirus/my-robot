import { Inject, Injectable, Logger } from '@nestjs/common';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import type { WebSocket as WsClient } from 'ws';

import { APP_CONFIG, type AppConfig, toWsUrl } from '../config/configuration';
import { handleSmartTtsWs } from './relay';

@Injectable()
export class WsRegistrar {
  private readonly logger = new Logger('WsRegistrar');

  constructor(@Inject(APP_CONFIG) private readonly config: AppConfig) { }

  register(fastify: FastifyInstance): void {
    fastify.route({
      method: 'GET',
      url: '/api/smart-tts/ws',
      handler: () => undefined,
      wsHandler: (socket, request) => {
        handleSmartTtsWs(
          socket as WsClient,
          { query: ((request as FastifyRequest).query ?? {}) as Record<string, unknown> },
          { aiServiceWsUrl: toWsUrl(this.config.AI_SERVICE_URL) },
        );
      },
    });
    this.logger.log('WS route /api/smart-tts/ws registered');
  }
}
