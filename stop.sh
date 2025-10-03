#!/bin/sh

# 在遇到任何错误时立即退出
set -e

echo "🛑 Initiating shutdown sequence..."

# Step 1: 停止并移除 docker-compose 服务
# 使用 'down -v' 会移除 compose 文件中定义的命名卷 (gateway_data, virtual_disks)
# 如果希望保留这些数据，请使用 'down'
echo ""
echo "🤚 [Step 1/3] Stopping docker-compose services..."
docker-compose down

# Step 2: 查找并强制移除所有动态创建的 worker 容器
echo ""
echo "🔥 [Step 2/3] Finding and forcibly removing all dynamic workers..."
WORKER_IDS=$(docker ps -a -q --filter "label=managed-by=code-interpreter-gateway")
if [ -n "$WORKER_IDS" ]; then
    # 在一行上静默移除所有 worker
    docker rm -f $WORKER_IDS > /dev/null
    echo "   -> All dynamic workers have been removed."
else
    echo "   -> No dynamically created workers found."
fi

# Step 3: 清理 Docker 网络
# docker-compose down 通常会处理，但这是一个额外的保险
echo ""
echo "🌐 [Step 3/3] Pruning unused networks..."
docker network prune -f --filter "label=com.docker.compose.project"

echo ""
echo "✅ Shutdown and cleanup complete."
