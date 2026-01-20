"""
Execute-related models for Worker service.
"""
from .base import ModelBase


class ExecuteRequest(ModelBase):
    """Request to execute Python code."""
    code: str


class ExecuteResponse(ModelBase):
    """Response from code execution."""
    result_text: str | None = None
    result_base64: str | None = None


class HealthResponse(ModelBase):
    """Health check response."""
    status: str
