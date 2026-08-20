import { z } from 'zod';

const EnvSchema = z.object({
  BFF_PORT: z.coerce.number().int().positive().default(5175),
  BFF_HOST: z.string().default('0.0.0.0'),
  AI_SERVICE_URL: z
    .string()
    .url()
    .default('http://localhost:8000')
    .transform((s) => s.replace(/\/+$/, '')),
  LOG_LEVEL: z
    .enum(['error', 'warn', 'info', 'debug', 'verbose'])
    .default('info'),
  CORS_ORIGINS: z
    .string()
    .default('["http://localhost:5173","http://localhost:5174"]')
    .transform((s) => {
      try {
        const parsed = JSON.parse(s);
        return Array.isArray(parsed) ? parsed.map(String) : [];
      } catch {
        return s.split(',').map((x) => x.trim()).filter(Boolean);
      }
    }),
});

export type AppConfig = z.infer<typeof EnvSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  return EnvSchema.parse(env);
}

export const APP_CONFIG = Symbol('APP_CONFIG');

export function toWsUrl(httpUrl: string): string {
  return httpUrl.replace(/^http/i, 'ws');
}
