# start.ps1

# Set the script to exit immediately if any command fails
$ErrorActionPreference = "Stop"

# --- Check if already running ---
$containerName = "code-interpreter_gateway"
Write-Host "🔎 Checking status of container '$containerName'..."

$gatewayId = docker ps -q --filter "name=^${containerName}$"

if ($gatewayId) {
    Write-Host "✅ The Code Interpreter gateway is already running. No action taken." -ForegroundColor Green
    Write-Host "`n🔑 Retrieving existing Auth Token..." -ForegroundColor Cyan
    $token = docker exec $containerName cat /gateway/auth_token.txt
    Write-Host "Your Auth Token is: $token" -BackgroundColor Green -ForegroundColor Black
    exit 0
} else {
    Write-Host "   -> Container is not running. Proceeding with startup."
}

# --- Step 1: Start Docker Compose ---
Write-Host "`n🚀 [Step 1/3] Starting the Code Interpreter environment..." -ForegroundColor Green
docker-compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ docker-compose up failed. Please check the logs." -ForegroundColor Red
    exit 1
}

# --- Step 2: Clean up builder container ---
Write-Host "`n🧹 [Step 2/3] Cleaning up the temporary builder container..." -ForegroundColor Cyan

$builderId = docker ps -a -q --filter "name=code-interpreter_worker_builder"

if ($builderId) {
    Write-Host "   -> Found builder container. Removing it..."
    docker rm $builderId | Out-Null
    Write-Host "   -> Builder container successfully removed." -ForegroundColor Green
} else {
    Write-Host "   -> No temporary builder container found to clean up. Skipping." -ForegroundColor Yellow
}

# --- Step 3: Wait for and retrieve the Auth Token ---
Write-Host "`n🔑 [Step 3/3] Waiting for Gateway to generate the Auth Token..." -ForegroundColor Cyan

$token = $null
# Poll for 30 seconds for the token file to be created
for ($i = 1; $i -le 30; $i++) {
    try {
        $token = docker exec $containerName cat /gateway/auth_token.txt
        if ($token) {
            break
        }
    } catch {
        # This block catches the error from the failed docker exec.
        # We do nothing here, which allows the loop to continue to the next poll.
    }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 1
}

Write-Host "" # Newline after the dots

if (-not $token) {
    Write-Host "`n❌ Timed out waiting for the Auth Token." -ForegroundColor Red
    Write-Host "   Please check the gateway container logs with: docker logs $containerName" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Token successfully retrieved!" -ForegroundColor Green
Write-Host "`n🎉 Startup complete. The system is ready." -ForegroundColor Green
Write-Host "Your Auth Token is: $token" -BackgroundColor Green -ForegroundColor Black
