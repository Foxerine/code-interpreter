"""
Status response model.
"""
from .base import ModelBase


class StatusResponse(ModelBase):
    total_workers: int
    busy_workers: int
    is_initializing: bool
