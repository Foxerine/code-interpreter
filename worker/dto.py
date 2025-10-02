"""Data Transfer Objects (DTOs) for the Python Code Interpreter API."""
from typing import Literal

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """Defines the structure for a Python code execution request."""
    code: str


class ExecuteResponse(BaseModel):
    """Defines the structure for a code execution response."""
    result_text: str | None = None
    result_base64: str | None = None


class HealthDetail(BaseModel):
    """Describes the health status of a single internal service."""
    status: str
    detail: str


class HealthStatus(BaseModel):
    """Describes the overall health of the container."""
    status: str
    services: dict[str, HealthDetail]

class ExecutionResult(BaseModel):
    """代码执行结果的 DTO"""
    status: Literal["ok", "error", "timeout", 'kernel_error']
    type: Literal["text", "image_png_base64", "connection_error", "execution_error", "timeout_error", "processing_error"]
    value: str | None = None
