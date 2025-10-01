#!/bin/sh

# 设置在遇到错误时立即退出
set -e

# 从环境变量中获取要监听的IP地址。
# 如果环境变量未设置，则为了安全起见，回退到只监听本地回环地址，
# 这将导致外部无法访问，从而明确地暴露配置错误。
LISTEN_IP=${GATEWAY_EXTERNAL_IP:-"127.0.0.1"}

echo "🚀 Starting Gateway..."
echo "🔒 Uvicorn will listen exclusively on IP: $LISTEN_IP"

# 使用 exec 来让 Uvicorn 进程替换掉 shell 进程。
# 这很重要，因为它确保了 Uvicorn 能正确接收到来自 Docker 的停止信号 (SIGTERM)。
exec uvicorn main:app --host "$LISTEN_IP" --port 3874
