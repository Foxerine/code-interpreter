#!/bin/sh

# 高配电脑 + 带网络
# 适用场景: 16核+ / 32GB+ RAM 的高配置机器，Worker 可访问互联网
# Recommended: 16+ cores / 32GB+ RAM machines with internet access for workers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/start.sh" \
    --min-idle-workers 5 \
    --max-total-workers 20 \
    --worker-cpu 2.0 \
    --worker-ram-mb 2048 \
    --worker-disk-mb 2500 \
    --enable-internet \
    "$@"
