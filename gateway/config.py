# gateway/config.py
import os
import uuid
from pathlib import Path

# --- Authentication ---
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

# --- Network & Naming ---
INTERNAL_NETWORK_NAME: str = os.environ.get("INTERNAL_NETWORK_NAME", "code-interpreter_workers_isolated_net")
WORKER_IMAGE_NAME: str = "code-interpreter-worker:latest"
GATEWAY_INTERNAL_IP = os.environ.get("GATEWAY_INTERNAL_IP", "172.28.0.2")

# --- Pool & Resource Configuration (now from environment variables) ---

# Pool Sizing
MIN_IDLE_WORKERS: int = int(os.environ.get("MIN_IDLE_WORKERS", 20))
MAX_TOTAL_WORKERS: int = int(os.environ.get("MAX_TOTAL_WORKERS", 100))

# Per-Worker Resource Limits
WORKER_CPU: float = float(os.environ.get("WORKER_CPU", 1.0)) # CPU cores
WORKER_RAM_MB: int = int(os.environ.get("WORKER_RAM_MB", 1024)) # Memory in MB
WORKER_MAX_DISK_SIZE_MB: int = int(os.environ.get("WORKER_MAX_DISK_SIZE_MB", 500)) # Virtual disk size in MB

# --- Timeout Configuration ---
WORKER_IDLE_TIMEOUT: int = int(os.environ.get("WORKER_IDLE_TIMEOUT", 3600))  # 1 hour
RECYCLING_INTERVAL: int = int(os.environ.get("RECYCLING_INTERVAL", 300))  # 5 minutes
MAX_EXECUTION_TIMEOUT: float = float(os.environ.get("MAX_EXECUTION_TIMEOUT", 15.0)) # 15 secs
