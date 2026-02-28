#!/bin/sh

# 低配电脑 + 不带网络
# 适用场景: 4核 / 8GB RAM 的低配置机器，Worker 无法访问互联网（更安全）
# Recommended: 4 cores / 8GB RAM machines without internet access (more secure)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/start.sh" \
    --min-idle-workers 1 \
    --max-total-workers 3 \
    --worker-cpu 1.0 \
    --worker-ram-mb 1024 \
    --worker-disk-mb 256 \
    "$@"
