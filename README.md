# my-robot

Monorepo containing H5 Vue applications and a Python AI backend service.

## Structure

```
my-robot/
├── apps/
│   ├── h5-app2/        # H5 page two (Vue 3 + Vite)
│   ├── bff/            # Node BFF (NestJS + Fastify, port 5175)
│   └── ai-service/     # Python AI backend service (FastAPI)
├── packages/
│   ├── shared-types/   # Shared TypeScript types
│   ├── ui/             # Shared Vue UI components
│   └── eslint-config/  # Shared ESLint config
└── tools/
    └── scripts/        # Workspace helper scripts
```

## Prerequisites

- Node.js >= 18
- pnpm >= 9
- Python >= 3.11

## Getting Started

```bash
# Install JS dependencies
pnpm install

# Run all apps in dev mode
pnpm dev

# Build everything
pnpm build
```

The Python service lives in `apps/ai-service`. See its own README for setup.
