#!/bin/sh

# 中配电脑 + 带网络
# 适用场景: 8核 / 16GB RAM 的中等配置机器，Worker 可访问互联网
# Recommended: 8 cores / 16GB RAM machines with internet access for workers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/start.sh" \
    --min-idle-workers 3 \
    --max-total-workers 10 \
    --worker-cpu 1.5 \
    --worker-ram-mb 1536 \
    --worker-disk-mb 500 \
    --enable-internet \
    "$@"
