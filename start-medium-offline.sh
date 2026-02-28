#!/bin/sh

# 中配电脑 + 不带网络
# 适用场景: 8核 / 16GB RAM 的中等配置机器，Worker 无法访问互联网（更安全）
# Recommended: 8 cores / 16GB RAM machines without internet access (more secure)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/start.sh" \
    --min-idle-workers 3 \
    --max-total-workers 10 \
    --worker-cpu 1.5 \
    --worker-ram-mb 1536 \
    --worker-disk-mb 500 \
    "$@"
