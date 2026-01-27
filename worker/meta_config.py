# worker/meta_config.py
"""
Configuration management for the worker service.

This module provides centralized configuration for the Jupyter kernel worker.
"""
import os


# --- Jupyter Kernel Configuration ---
JUPYTER_HOST: str = os.environ.get("JUPYTER_HOST", "127.0.0.1:8888")
JUPYTER_API_URL: str = f"http://{JUPYTER_HOST}"
JUPYTER_WS_URL: str = f"ws://{JUPYTER_HOST}"

# --- Execution Configuration ---
EXECUTION_TIMEOUT: float = float(os.environ.get("EXECUTION_TIMEOUT", 120.0))  # 120 seconds default

# --- Kernel Startup Configuration ---
KERNEL_START_MAX_RETRIES: int = int(os.environ.get("KERNEL_START_MAX_RETRIES", 10))
KERNEL_START_RETRY_DELAY: float = float(os.environ.get("KERNEL_START_RETRY_DELAY", 1.0))
KERNEL_API_TIMEOUT: float = float(os.environ.get("KERNEL_API_TIMEOUT", 5.0))

# --- Supervisor Configuration ---
SUPERVISOR_RPC_URL: str = os.environ.get("SUPERVISOR_RPC_URL", "http://127.0.0.1:9001/RPC2")

# --- Matplotlib Configuration ---
MATPLOTLIB_FONT_FAMILY: str = os.environ.get("MATPLOTLIB_FONT_FAMILY", "SimHei")
