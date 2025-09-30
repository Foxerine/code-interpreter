# start.ps1

# 设置脚本在遇到错误时立即停止
$ErrorActionPreference = "Stop"

Write-Host "🚀 [Step 1/2] Starting the Code Interpreter environment..." -ForegroundColor Green
# 使用 --build 确保镜像总是最新的
# 使用 -d 在后台运行
docker-compose up --build -d

# 检查上一个命令是否成功
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ docker-compose up failed. Please check the logs." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Environment started. Gateway is running." -ForegroundColor Green
Write-Host "🧹 [Step 2/2] Cleaning up the temporary builder container..." -ForegroundColor Cyan

# 查找名为 code-interpreter_worker_builder 的容器
$builderId = docker ps -a -q --filter "name=code-interpreter_worker_builder"

if ($builderId) {
    Write-Host "   -> Found builder container. Removing it..."
    docker rm $builderId | Out-Null
    Write-Host "   -> Builder container successfully removed." -ForegroundColor Green
} else {
    Write-Host "   -> No temporary builder container found to clean up. Skipping." -ForegroundColor Yellow
}

Write-Host "🎉 Startup complete. The system is ready."
