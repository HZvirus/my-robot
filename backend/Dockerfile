# 机器人平台后端统一镜像（uv workspaces）
# 各服务复用同一镜像，通过 command 覆盖启动模块。
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先拷贝依赖清单以利用缓存
COPY pyproject.toml ./
COPY libs ./libs
COPY services ./services

# 同步整个 workspace（所有包 + 默认依赖；不装 dev 组）
RUN uv sync --all-packages --no-dev

# 默认启动 user-tenant，compose 中用 command 覆盖
CMD ["python", "-m", "user_tenant.main"]
