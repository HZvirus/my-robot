# 机器人平台一键开发脚本（Windows PowerShell）
# 用法：.\scripts\dev.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1. 准备 .env
if (-not (Test-Path 'deploy\.env')) {
    Copy-Item 'deploy\.env.example' 'deploy\.env'
    Write-Host '已生成 deploy\.env（可按需修改）'
}

# 2. 启动后端 + 基础设施
Write-Host '==> 启动后端服务（docker compose up -d --build）...' -ForegroundColor Cyan
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
if ($LASTEXITCODE -ne 0) { throw 'docker compose 启动失败' }

# 3. 前端依赖
Write-Host '==> 安装前端依赖（pnpm install）...' -ForegroundColor Cyan
Push-Location frontend
try {
    if (-not (Test-Path 'node_modules')) { pnpm install }
} finally { Pop-Location }

# 4. 启动两个 H5 dev server（新窗口）
Write-Host '==> 启动前端 dev server（hospital:5173 / home:5174）...' -ForegroundColor Cyan
Start-Process cmd -ArgumentList '/k', "cd /d $root\frontend && pnpm dev:hospital"
Start-Process cmd -ArgumentList '/k', "cd /d $root\frontend && pnpm dev:home"

Write-Host ''
Write-Host '完成！' -ForegroundColor Green
Write-Host '  医院大屏:  http://localhost:5173'
Write-Host '  家庭小屏:  http://localhost:5174'
Write-Host '  Kong 网关: http://localhost:8000'
Write-Host '  EMQX 控制台: http://localhost:18083 (admin/public)'
Write-Host ''
Write-Host '查看后端日志: docker compose -f deploy/docker-compose.yml logs -f'
Write-Host '停止: docker compose -f deploy/docker-compose.yml down'
