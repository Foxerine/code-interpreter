# stop.ps1 - Stops and thoroughly cleans up all related Docker resources

# --- Self-elevation to Administrator ---
$currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "This script needs Administrator privileges to manage Docker containers and volumes." -ForegroundColor Yellow
    # Relaunch the script with Admin rights
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoExit", "-File", "`"$PSCommandPath`""
    exit
}

# Ensure that any command failure will immediately stop the script
$ErrorActionPreference = "Stop"

try {
    Write-Host "`n🛑 Initiating shutdown and cleanup sequence..." -ForegroundColor Cyan

    # Step 1: Stop and remove docker-compose services
    # The 'down' command stops and removes containers and networks.
    Write-Host "`n🤚 [Step 1/3] Stopping docker-compose services..." -ForegroundColor White
    docker-compose down

    # Step 2: Find and forcibly remove all dynamically created worker containers
    Write-Host "`n🔥 [Step 2/3] Finding and forcibly removing all dynamic workers..." -ForegroundColor White
    # Use the exact same filter as the .sh script to find gateway-managed containers
    $workerIds = docker ps -a -q --filter "label=managed-by=code-interpreter-gateway"

    if (-not [string]::IsNullOrWhiteSpace($workerIds)) {
        # If workers are found, pass them to the docker rm -f command
        docker rm -f $workerIds
        Write-Host "   -> ✅ All dynamic workers have been removed." -ForegroundColor Green
    } else {
        Write-Host "   -> ℹ️ No dynamically created workers found." -ForegroundColor Gray
    }

    # Step 3: Prune Docker networks
    # docker-compose down usually handles this, but this is an extra safety measure for any orphaned networks.
    Write-Host "`n🌐 [Step 3/3] Pruning unused networks..." -ForegroundColor White
    docker network prune -f --filter "label=com.docker.compose.project"

    Write-Host "`n🎉 Cleanup complete. All resources have been successfully released." -ForegroundColor Green
}
catch {
    # Catch any errors that occur during execution
    Write-Host "`n❌ An error occurred during shutdown: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Please check the output above for more details." -ForegroundColor Yellow
}
