# gateway/config.py

"""
Centralized configuration for the Gateway service.
"""
import os
import uuid
from pathlib import Path

from loguru import logger as l

# --- Authentication ---
# The master token required to use the gateway services.
def get_auth_token():
    token_file = Path("/gateway/auth_token.txt")
    if "AUTH_TOKEN" in os.environ:
        return os.environ["AUTH_TOKEN"]
    elif token_file.exists():
        return token_file.read_text().strip()
    else:
        new_token = str(uuid.uuid4())
        token_file.write_text(new_token)
        return new_token

AUTH_TOKEN: str = get_auth_token()

# --- Worker Management ---
# The name of the Docker Compose service defined for the worker
WORKER_SERVICE_NAME: str = "code-interpreter_worker"

# The name of the internal Docker network workers and the gateway share
# [更新] 更改为新的隔离网络名称
INTERNAL_NETWORK_NAME: str = os.environ.get("INTERNAL_NETWORK_NAME", "code-interpreter_workers_isolated_net")

# The image to use for creating new worker containers.
# This should match the image built for the worker service.
WORKER_IMAGE_NAME: str = "code-interpreter-worker:latest" # Docker compose creates this image name

# --- Pool Sizing ---
# The minimum number of idle workers to keep ready in the pool.
MIN_IDLE_WORKERS: int = 5

# The absolute maximum number of concurrent workers allowed.
MAX_TOTAL_WORKERS: int = 30

# --- Timeout ---
# Time in seconds a worker can be idle (not executing code) before being recycled.
WORKER_IDLE_TIMEOUT: int = 3600  # 1 hour

# How often the background task runs to check for timed-out workers.
RECYCLING_INTERVAL: int = 300  # 5 minutes

MAX_EXECUTION_TIMEOUT: float = 15.0 # 15 secs

GATEWAY_INTERNAL_IP = os.environ.get("GATEWAY_INTERNAL_IP", "172.28.0.2")
