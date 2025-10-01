# start.ps1

# 设置脚本在遇到错误时立即停止
$ErrorActionPreference = "Stop"

# --- 新增检查 ---
$containerName = "code-interpreter_gateway"
Write-Host "🔎 Checking status of container '$containerName'..."

# 检查网关容器是否已经在运行。docker ps -q 的输出在 PowerShell 中是字符串
# 如果容器存在，变量 $gatewayId 将包含容器ID（非空字符串），if 会判断为 true
$gatewayId = docker ps -q --filter "name=^${containerName}$"

if ($gatewayId) {
    Write-Host "✅ The Code Interpreter gateway is already running. No action taken." -ForegroundColor Green
    exit 0
} else {
    Write-Host "   -> Container is not running. Proceeding with startup."
}
# --- 检查结束 ---


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
