#!/bin/bash

# 这个脚本用于彻底关闭并清理 Code Interpreter 环境。
# 我们不使用 'set -e'，因为清理脚本应该尝试执行所有步骤，即使其中一步失败。

echo "🛑 Initiating shutdown sequence for the Code Interpreter environment..."

echo "🤚 [Step 1/3] Stopping gateway to prevent new workers from being created..."
# 第一次 down 会停止并移除 gateway。
# 如果 worker 还在运行，网络可能无法被移除，这没关系，后续步骤会处理。
# --remove-orphans 可以清理掉任何不属于 compose 文件但属于项目历史的容器。
docker-compose down --remove-orphans > /dev/null 2>&1
echo "   -> Gateway stopped."

echo "🔥 [Step 2/3] Finding and forcibly removing all dynamically created worker containers..."
# 通过标签查找所有由 WorkerManager 创建的容器
WORKER_IDS=$(docker ps -a -q --filter "label=managed-by=code-interpreter-gateway")

if [[ -n "$WORKER_IDS" ]]; then
    echo "   -> Found dynamically created workers. Removing them now..."
    # 使用 xargs 可以安全地处理多个容器ID（即使它们之间有换行符）
    # 使用 -f 强制删除正在运行的容器
    echo "$WORKER_IDS" | xargs docker rm -f > /dev/null
    echo "   -> All dynamic workers have been removed."
else
    echo "   -> No dynamically created workers found to clean up."
fi

echo "🧹 [Step 3/3] Final cleanup of network and other resources..."
# 既然所有 worker 都已经被移除，这次 down 将能够成功清理掉网络和 builder 容器
docker-compose down --remove-orphans > /dev/null 2>&1
echo "   -> Network and remaining resources have been cleaned up."

echo "✅ Shutdown and cleanup complete."
