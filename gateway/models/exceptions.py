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


class BatchFileOperationError(WorkerPoolError):
    """Raised when batch file upload/export operations fail."""
    def __init__(self, operation: str, failed_count: int, total_count: int, first_error: str):
        self.operation = operation
        self.failed_count = failed_count
        self.total_count = total_count
        self.first_error = first_error
        self.message = f"{operation} failed for {failed_count}/{total_count} file(s)"
        super().__init__(self.message)
