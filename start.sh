#!/bin/sh

# 在遇到任何错误时立即退出
set -e

# --- Step 1: 检查网关容器是否已在运行 ---
CONTAINER_NAME="code-interpreter_gateway"
echo "🔎 Checking status of container '$CONTAINER_NAME'..."
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

# --- Step 2: 启动 Docker Compose ---
echo ""
echo "🚀 Starting the Code Interpreter environment..."
docker-compose up --build -d

# --- Step 3: 清理临时的 builder 容器 ---
BUILDER_ID=$(docker ps -a -q --filter "name=code-interpreter_worker_builder")
if [ -n "$BUILDER_ID" ]; then
    echo ""
    echo "🧹 Cleaning up the temporary builder container..."
    docker rm "$BUILDER_ID" > /dev/null
    echo "   -> Builder container successfully removed."
fi

# --- Step 4: 等待并获取 Auth Token ---
echo ""
echo "🔑 Waiting for Gateway to generate the Auth Token..."

i=1
while [ $i -le 30 ]; do
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
