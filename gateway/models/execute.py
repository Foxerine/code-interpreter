"""
Execute-related models.
"""
from pydantic import Field

from .base import ModelBase


class ExecuteRequest(ModelBase):
    """Request to execute code in sandbox."""
    code: str = Field(max_length=209_715_200)
    """Python code to execute (200MB limit for file upload support)"""


class ExecuteResponse(ModelBase):
    """Response from code execution."""
    result_text: str | None = None
    """Text output from execution"""
    result_base64: str | None = None
    """Base64 encoded image output (if any)"""


