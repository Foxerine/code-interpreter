# start.ps1 - Ultimate Environment Setup Wizard & Starter (v15.0 - Configurable)

[CmdletBinding()]
param(
# 最小空闲工作实例数
    [int]$MinIdleWorkers = 15,

# 允许创建的最大工作实例总数
    [int]$MaxTotalWorkers = 50,

# 每个工作实例的CPU核心数限制 (例如: 1.0, 1.5, 2.0)
    [double]$WorkerCPU = 1.0,

# 每个工作实例的内存限制 (单位: MB)
    [int]$WorkerRAM_MB = 1024,

# 每个工作实例的虚拟磁盘大小 (单位: MB)
    [int]$WorkerDisk_MB = 500
)

# --- 自我提升为管理员权限 ---
$currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "This script needs Administrator privileges to manage Docker." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoExit", "-File", "`"$PSCommandPath`""
    exit
}

$ErrorActionPreference = "Stop"

# ==============================================================================
# 将脚本参数设置为环境变量，以便 Docker Compose 可以使用它们
# ==============================================================================
$env:MIN_IDLE_WORKERS = $MinIdleWorkers
$env:MAX_TOTAL_WORKERS = $MaxTotalWorkers
$env:WORKER_CPU = $WorkerCPU
$env:WORKER_RAM_MB = $WorkerRAM_MB
$env:WORKER_MAX_DISK_SIZE_MB = $WorkerDisk_MB

Write-Host "`n⚙️  Applying Configuration:" -ForegroundColor Cyan
Write-Host "   - Min Idle Workers      : $env:MIN_IDLE_WORKERS"
Write-Host "   - Max Total Workers     : $env:MAX_TOTAL_WORKERS"
Write-Host "   - Worker CPU Limit      : $env:WORKER_CPU cores"
Write-Host "   - Worker RAM Limit      : $env:WORKER_RAM_MB MB"
Write-Host "   - Worker Disk Size      : $env:WORKER_MAX_DISK_SIZE_MB MB"


# ==============================================================================
# PHASE 1: 验证环境
# ==============================================================================
Write-Host "`n🔎 [Phase 1/3] Validating Your Environment..." -ForegroundColor Cyan

function Test-Docker-Environment {
    try { wsl.exe --status >$null 2>$null; if ($LASTEXITCODE -ne 0) { throw "WSL is not installed." } } catch { return "WslNotInstalled" }
    docker version >$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        if (Get-Command docker -ErrorAction SilentlyContinue) { return "DockerNotRunning" }
        else { return "DockerNotInstalled" }
    }
    return "OK"
}

while ($true) {
    $envStatus = Test-Docker-Environment
    if ($envStatus -eq "OK") { Write-Host "   -> ✅ Environment is ready!"; break }
    Write-Host "`n⚠️  ACTION REQUIRED:" -ForegroundColor Yellow
    switch ($envStatus) {
        "WslNotInstalled" { Write-Host "   Please enable WSL: Open Admin PowerShell, run 'wsl --install', then REBOOT." }
        "DockerNotInstalled" { Write-Host "   Please install Docker Desktop from https://www.docker.com" }
        "DockerNotRunning" { Write-Host "   Please start Docker Desktop and wait for it to initialize." }
    }
    Read-Host -Prompt "Press Enter to re-check"
}

# ==============================================================================
# PHASE 2: 启动应用
# ==============================================================================
Write-Host "`n🚀 [Phase 2/3] Starting application via Docker Compose..." -ForegroundColor Cyan

try {
    $containerName = "code-interpreter_gateway"
    $token = ""
    $gatewayId = docker ps -q --filter "name=^$containerName$"

    if (-not [string]::IsNullOrWhiteSpace($gatewayId)) {
        Write-Host "✅ The gateway is already running."
        $token = (docker exec $containerName cat /gateway/auth_token.txt).Trim()
    } else {
        Write-Host "   -> Container is not running. Building and starting services..."
        docker-compose up --build -d

        $builderId = docker ps -a -q --filter "name=code-interpreter_worker_builder"
        if (-not [string]::IsNullOrWhiteSpace($builderId)) {
            Write-Host "🧹 Cleaning up the temporary builder container..."
            docker rm $builderId > $null
        }

        Write-Host -n "🔑 Waiting for Gateway to generate the Auth Token..."
        $i = 1
        while ($i -le 30) {
            try {
                $tokenOutput = docker exec $containerName cat /gateway/auth_token.txt 2>$null
                if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($tokenOutput)) {
                    $token = $tokenOutput.Trim(); Write-Host ""; break
                }
            } catch {}
            Write-Host -n "."; Start-Sleep -Seconds 1; $i++
        }

        if ([string]::IsNullOrWhiteSpace($token)) {
            throw "Timed out waiting for the Auth Token."
        }
    }

    Write-Host "`n🎉 Startup complete. The system is ready." -ForegroundColor Green
    Write-Host "   Your Auth Token is: $token"
}
catch {
    Write-Host "`n❌ An error occurred during startup: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Showing last 50 lines of gateway logs:" -ForegroundColor Yellow
    try { docker-compose logs --tail=50 code-interpreter_gateway } catch {}
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# ==============================================================================
# PHASE 3: 完成
# ==============================================================================
Write-Host "`n✅ [Phase 3/3] The application has been started successfully." -ForegroundColor Green
