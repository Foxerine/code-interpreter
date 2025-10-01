#!/bin/bash

# 设置脚本在遇到错误时立即停止
set -e

# --- 新增检查 ---
# 定义关键容器的名称，以便于未来修改
CONTAINER_NAME="code-interpreter_gateway"

echo "🔎 Checking status of container '$CONTAINER_NAME'..."

# 检查网关容器是否已经在运行
# 使用 -q 只输出ID，使用正则表达式 `^...$` 进行精确匹配
GATEWAY_ID=$(docker ps -q --filter "name=^${CONTAINER_NAME}$")

if [[ -n "$GATEWAY_ID" ]]; then
    echo "✅ The Code Interpreter gateway is already running. No action taken."
    exit 0
else
    echo "   -> Container is not running. Proceeding with startup."
fi
# --- 检查结束 ---


echo "🚀 [Step 1/2] Starting the Code Interpreter environment..."
# 使用 --build 确保镜像总是最新的
# 使用 -d 在后台运行
docker-compose up --build -d

echo "✅ Environment started. Gateway is running."
echo "🧹 [Step 2/2] Cleaning up the temporary builder container..."

# 查找名为 code-interpreter_worker_builder 的容器
BUILDER_ID=$(docker ps -a -q --filter "name=code-interpreter_worker_builder")

if [[ -n "$BUILDER_ID" ]]; then
    echo "   -> Found builder container. Removing it..."
    docker rm "$BUILDER_ID" > /dev/null
    echo "   -> Builder container successfully removed."
else
    echo "   -> No temporary builder container found to clean up. Skipping."
fi

echo "🎉 Startup complete. The system is ready."
echo "🔑 To get your auth token, check gateway container log or run: docker exec code-interpreter_gateway cat /gateway/auth_token.txt"
