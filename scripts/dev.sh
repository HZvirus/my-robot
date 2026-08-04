#!/usr/bin/env bash
# 机器人平台一键开发脚本（Bash / WSL / Linux / macOS）
# 用法：./scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1. 准备 .env
if [ ! -f deploy/.env ]; then
    cp deploy/.env.example deploy/.env
    echo "已生成 deploy/.env（可按需修改）"
fi

# 2. 启动后端 + 基础设施
echo -e "\033[36m==> 启动后端服务（docker compose up -d --build）...\033[0m"
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build

# 3. 前端依赖
echo -e "\033[36m==> 安装前端依赖（pnpm install）...\033[0m"
cd frontend
[ -d node_modules ] || pnpm install

# 4. 启动两个 H5 dev server（前台）
echo -e "\033[36m==> 启动前端 dev server（hospital:5173 / home:5174），Ctrl+C 退出...\033[0m"
pnpm dev:hospital &
HOSP_PID=$!
pnpm dev:home &
HOME_PID=$!

cleanup() {
    kill "$HOSP_PID" "$HOME_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo -e "\033[32m完成！\033[0m"
echo "  医院大屏:   http://localhost:5173"
echo "  家庭小屏:   http://localhost:5174"
echo "  Kong 网关:  http://localhost:8000"
echo "  EMQX 控制台: http://localhost:18083 (admin/public)"
echo ""
echo "查看后端日志: docker compose -f deploy/docker-compose.yml logs -f"
echo "停止: docker compose -f deploy/docker-compose.yml down"

wait
