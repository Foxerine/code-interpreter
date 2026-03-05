#!/bin/sh

# start.sh - Ultimate Environment Setup Wizard & Starter (v15.0 - Configurable)

# 在遇到任何错误时立即退出
set -e

# --- ⚙️ 默认配置 ---
# NOTE: Increased resource limits to support Node.js, LibreOffice, and Playwright
# TODO: [OPTIMIZATION] Consider adding --lightweight flag for minimal deployments
AUTH_TOKEN=""
MIN_IDLE_WORKERS=10
MAX_TOTAL_WORKERS=50
WORKER_CPU=1.5
WORKER_RAM_MB=1536
WORKER_MAX_DISK_SIZE_MB=500
WORKER_INTERNET_ACCESS=false
BUILD_MODE=false
IMAGE_TAG="latest"

# --- 🔄 解析命令行参数 ---
# 循环遍历所有传入的参数
while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-key) AUTH_TOKEN="$2"; shift 2;;
    --min-idle-workers) MIN_IDLE_WORKERS="$2"; shift 2;;
    --max-total-workers) MAX_TOTAL_WORKERS="$2"; shift 2;;
    --worker-cpu) WORKER_CPU="$2"; shift 2;;
    --worker-ram-mb) WORKER_RAM_MB="$2"; shift 2;;
    --worker-disk-mb) WORKER_MAX_DISK_SIZE_MB="$2"; shift 2;;
    --enable-internet) WORKER_INTERNET_ACCESS=true; shift;;
    --build) BUILD_MODE=true; shift;;
    --image-tag) IMAGE_TAG="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --api-key <string>          Custom API key (auto-generated if not set)"
      echo "  --min-idle-workers <num>    Minimum number of idle workers (default: 10)"
      echo "  --max-total-workers <num>   Maximum number of total workers (default: 50)"
      echo "  --worker-cpu <float>        CPU cores per worker (default: 1.5)"
      echo "  --worker-ram-mb <int>       RAM in MB per worker (default: 1536)"
      echo "  --worker-disk-mb <int>      Virtual disk size in MB per worker (default: 500)"
      echo "  --enable-internet           Enable internet access for workers (SECURITY RISK!)"
      echo "  --build                    Force local build instead of pulling from registry"
      echo "  --image-tag <tag>          Image tag to use (default: latest)"
      echo "  -h, --help                  Show this help message"
      exit 0
      ;;
    *) echo "Unknown parameter passed: $1"; exit 1;;
  esac
done

# --- 🚀 导出配置为环境变量 ---
if [ -n "$AUTH_TOKEN" ]; then
    export AUTH_TOKEN
fi
export MIN_IDLE_WORKERS
export MAX_TOTAL_WORKERS
export WORKER_CPU
export WORKER_RAM_MB
export WORKER_MAX_DISK_SIZE_MB
export WORKER_INTERNET_ACCESS
export IMAGE_TAG

echo "⚙️  Applying Configuration:"
if [ -n "$AUTH_TOKEN" ]; then
    echo "   - API Key               : (custom)"
else
    echo "   - API Key               : (auto-generated)"
fi
echo "   - Min Idle Workers      : $MIN_IDLE_WORKERS"
echo "   - Max Total Workers     : $MAX_TOTAL_WORKERS"
echo "   - Worker CPU Limit      : $WORKER_CPU cores"
echo "   - Worker RAM Limit      : $WORKER_RAM_MB MB"
echo "   - Worker Disk Size      : $WORKER_MAX_DISK_SIZE_MB MB"
echo "   - Worker Internet Access: $WORKER_INTERNET_ACCESS"
echo "   - Image Tag             : $IMAGE_TAG"
echo "   - Build Mode            : $BUILD_MODE"

# Security warning for internet access
if [ "$WORKER_INTERNET_ACCESS" = "true" ]; then
    echo ""
    echo "⚠️  WARNING: Internet access is ENABLED for workers!"
    echo "   Security risks include:"
    echo "   - Attackers may download malicious tools"
    echo "   - Attackers may establish reverse shells"
    echo "   - Attackers may abuse network for attacks (DDoS, scanning, etc.)"
    echo "   - Private IPs are blocked, but public internet is fully accessible"
    echo "   By continuing, you accept all security consequences."
    echo ""
fi

# --- 🔎 检查网关容器是否已在运行 ---
CONTAINER_NAME="code-interpreter_gateway"
echo "\n🔎 Checking status of container '$CONTAINER_NAME'..."
GATEWAY_ID=$(docker ps -q --filter "name=^${CONTAINER_NAME}$")

if [ -n "$GATEWAY_ID" ]; then
    echo "✅ The Code Interpreter gateway is already running."
    echo ""
    echo "🔑 Retrieving existing Auth Token..."
    TOKEN=$(docker exec "$CONTAINER_NAME" cat /gateway/auth_token.txt)
    echo "   Your Auth Token is: $TOKEN"
    exit 0
fi
echo "   -> Container is not running. Proceeding with startup."

# --- 🐳 启动 Docker Compose ---
echo ""
if [ "$BUILD_MODE" = "true" ]; then
    echo "🔨 Building images locally and starting services..."
    docker-compose up --build -d
else
    echo "🚀 Pulling images from registry and starting services..."
    docker-compose pull
    docker-compose up -d
fi

# --- 🧹 清理临时的 builder 容器 ---
BUILDER_ID=$(docker ps -a -q --filter "name=code-interpreter_worker_builder")
if [ -n "$BUILDER_ID" ]; then
    echo ""
    echo "🧹 Cleaning up the temporary builder container..."
    docker rm "$BUILDER_ID" > /dev/null
    echo "   -> Builder container successfully removed."
fi

# --- 🔑 等待并获取 Auth Token ---
echo ""
echo "🔑 Waiting for Gateway to generate the Auth Token..."

i=1
while [ $i -le 30 ]; do
    # 使用 '|| true' 来防止在容器刚启动时 'docker exec' 失败导致脚本退出
    TOKEN=$(docker exec "$CONTAINER_NAME" cat /gateway/auth_token.txt 2>/dev/null || true)
    if [ -n "$TOKEN" ]; then
        echo ""
        echo "✅ Token successfully retrieved!"
        echo ""
        echo "🎉 Startup complete. The system is ready."
        echo "   Your Auth Token is: $TOKEN"
        exit 0
    fi
    printf "."
    sleep 1
    i=$((i + 1))
done

# 如果循环结束仍未获取到 Token
echo ""
echo "❌ Timed out waiting for the Auth Token." >&2
echo "   Showing last 50 lines of gateway logs for debugging:" >&2
docker-compose logs --tail=50 code-interpreter_gateway
exit 1
