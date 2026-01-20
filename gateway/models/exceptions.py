"""
Custom exceptions for the gateway models layer.

These exceptions are framework-agnostic and should be caught
by the FastAPI layer to convert to HTTP responses.
"""


class WorkerPoolError(Exception):
    """Base exception for WorkerPool operations."""
    pass


class WorkerPoolShuttingDownError(WorkerPoolError):
    """Raised when WorkerPool is shutting down."""
    def __init__(self, message: str = "Service is shutting down"):
        self.message = message
        super().__init__(self.message)


class WorkerProvisionError(WorkerPoolError):
    """Raised when a worker cannot be provisioned."""
    def __init__(self, message: str = "Could not provision a new worker environment"):
        self.message = message
        super().__init__(self.message)
