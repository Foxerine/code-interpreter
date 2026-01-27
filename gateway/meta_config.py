# gateway/meta_config.py
"""
Configuration management for the gateway service.

This module provides centralized configuration loaded from environment variables.
"""
import os
import secrets
from pathlib import Path


# --- Authentication ---
def get_auth_token() -> str:
    token_file = Path('/gateway/auth_token.txt')
    if 'AUTH_TOKEN' in os.environ and os.environ['AUTH_TOKEN']:
        token = os.environ['AUTH_TOKEN']
    elif token_file.exists():
        return token_file.read_text().strip()
    else:
        # Generate cryptographically secure token (32 bytes = 256 bits)
        token = secrets.token_urlsafe(32)
    # Always write token to file for start script to read
    token_file.write_text(token)
    token_file.chmod(0o600)  # Restrict file permissions to owner only
    return token


AUTH_TOKEN: str = get_auth_token()

# --- Network & Naming ---
INTERNAL_NETWORK_NAME: str = os.environ.get("INTERNAL_NETWORK_NAME", "code-interpreter_workers_isolated_net")
WORKER_IMAGE_NAME: str = "code-interpreter-worker:latest"
GATEWAY_INTERNAL_IP = os.environ.get("GATEWAY_INTERNAL_IP", "172.28.0.2")

# --- Pool & Resource Configuration (now from environment variables) ---
# TODO: [OPTIMIZATION] Consider dynamic resource allocation based on task type
# TODO: [FEATURE] Add support for separate worker pools (lightweight vs full-featured)

# Pool Sizing
# NOTE: Reduced from 20/100 to 10/50 due to increased per-worker resource requirements
# after adding Node.js, LibreOffice, and Playwright support
MIN_IDLE_WORKERS: int = int(os.environ.get("MIN_IDLE_WORKERS", 10))
MAX_TOTAL_WORKERS: int = int(os.environ.get("MAX_TOTAL_WORKERS", 50))

# Per-Worker Resource Limits
# NOTE: Increased from 1.0 CPU / 1024 MB RAM to accommodate:
# - Node.js runtime (~50-100 MB)
# - LibreOffice operations (~500-800 MB peak)
# - Playwright browser automation (~300-500 MB)
WORKER_CPU: float = float(os.environ.get("WORKER_CPU", 1.5))  # CPU cores
WORKER_RAM_MB: int = int(os.environ.get("WORKER_RAM_MB", 1536))  # Memory in MB
WORKER_MAX_DISK_SIZE_MB: int = int(os.environ.get("WORKER_MAX_DISK_SIZE_MB", 500))  # Virtual disk size in MB

# --- Timeout Configuration ---
WORKER_IDLE_TIMEOUT: int = int(os.environ.get("WORKER_IDLE_TIMEOUT", 3600))  # 1 hour
RECYCLING_INTERVAL: int = int(os.environ.get("RECYCLING_INTERVAL", 300))  # 5 minutes
MAX_EXECUTION_TIMEOUT: float = float(os.environ.get("MAX_EXECUTION_TIMEOUT", 120.0))  # 120 secs

# --- File Operation Limits ---
MAX_FILE_SIZE_MB: int = int(os.environ.get("MAX_FILE_SIZE_MB", 100))  # 100MB default

# --- Security ---
# SECURITY DESIGN: SSRF protection is configurable for environments where internal network
# access is required (e.g., downloading from internal object storage). Default is enabled.
SSRF_PROTECTION_ENABLED: bool = os.environ.get('SSRF_PROTECTION_ENABLED', 'true').lower() == 'true'

# SECURITY DESIGN: CORS default '*' is intentional for development/testing flexibility.
# Production deployments should set CORS_ALLOWED_ORIGINS to explicit origin list.
# Rate limiting is expected to be handled at infrastructure level (nginx, cloudflare, etc.).
_cors_origins_str: str = os.environ.get('CORS_ALLOWED_ORIGINS', '*')
CORS_ALLOWED_ORIGINS: list[str] = (
    ['*'] if _cors_origins_str == '*'
    else [origin.strip() for origin in _cors_origins_str.split(',') if origin.strip()]
)
