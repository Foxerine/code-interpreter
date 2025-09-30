#!/bin/bash

echo "🛑 Initiating shutdown sequence for the Code Interpreter environment..."

echo "🤚 [Step 1/3] Stopping the gateway container to prevent new workers..."
# 第一次 down 会停止并移除 gateway。网络删除失败是正常的，因为还有 worker 连着。
docker-compose down --remove-orphans > /dev/null 2>&1
echo "   -> Gateway stopped."

echo "🔥 [Step 2/3] Finding and forcibly removing all dynamically created workers..."
WORKER_IDS=$(docker ps -a -q --filter "label=managed-by=code-interpreter-gateway")

if [[ -n "$WORKER_IDS" ]]; then
    echo "   -> Found running worker containers. Removing them now..."
    # docker rm -f $WORKER_IDS 可能会因为换行符出问题，用 xargs 更稳健
    echo "$WORKER_IDS" | xargs docker rm -f > /dev/null
    echo "   -> All dynamic workers have been removed."
else
    echo "   -> No dynamically created workers found."
fi

echo "🧹 [Step 3/3] Final cleanup to remove the network..."
# 因为 worker 已经被清理，这次 down 将成功移除网络和 builder
docker-compose down --remove-orphans > /dev/null 2>&1
echo "   -> Network and remaining resources cleaned up."

echo "✅ Shutdown and cleanup complete."
