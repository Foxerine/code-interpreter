"""
Common models shared across the gateway.
"""
from .base import ModelBase


class ErrorDetail(ModelBase):
    """Error response detail."""
    detail: str
