# stop.ps1

# 设置脚本在遇到错误时继续执行，因为我们预期某些命令可能会“失败”
$ErrorActionPreference = "SilentlyContinue"

Write-Host "🛑 Initiating shutdown sequence for the Code Interpreter environment..." -ForegroundColor Yellow

Write-Host "🤚 [Step 1/3] Stopping the gateway container to prevent new workers..." -ForegroundColor Cyan
# 第一次 down 会停止并移除 gateway。网络删除失败是正常的。
docker-compose down
Write-Host "   -> Gateway stopped."

Write-Host "🔥 [Step 2/3] Finding and forcibly removing all dynamically created workers..." -ForegroundColor Cyan
$workerIds = docker ps -a -q --filter "label=managed-by=code-interpreter-gateway"

if ($workerIds) {
    Write-Host "   -> Found running worker containers. Removing them now..."
    docker rm -f $workerIds | Out-Null
    Write-Host "   -> All dynamic workers have been removed." -ForegroundColor Green
} else {
    Write-Host "   -> No dynamically created workers found." -ForegroundColor Yellow
}

Write-Host "🧹 [Step 3/3] Final cleanup to remove the network..." -ForegroundColor Cyan
# 因为 worker 已经被清理，这次 down 将成功移除网络
docker-compose down
Write-Host "   -> Network and remaining resources cleaned up."

Write-Host "✅ Shutdown and cleanup complete." -ForegroundColor Green

