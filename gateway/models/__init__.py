"""
Gateway models package.

This package contains all domain models for the gateway service,
following the Rich Domain Model pattern where domain objects
contain both data and behavior.
"""
from .base import ModelBase
from .field_types import (
    Str32,
    Str64,
    Str128,
    Str256,
    Str1024,
    Str1280,
    NonNegativeInt,
    PositiveInt,
    SandboxPathStr,
    SandboxFileName,
)
from .common import ErrorDetail
from .execute import ExecuteRequest, ExecuteResponse
from .files import (
    SandboxPath,
    SandboxFile,
    SandboxFileRefBase,
    FileUploadItem,
    FileUploadRequest,
    FileUploadResultItem,
    FileUploadResponse,
    FileExportItem,
    FileExportRequest,
    FileExportResultItem,
    FileExportResponse,
    FileRef,
    FileDeleteRequest,
    FileOperationError,
    PathSecurityError,
    FileTooLargeError,
    FileDownloadError,
)
from .worker import Worker, WorkerExecuteResult, WorkerExecuteResultData, WorkerPool, WorkerStatus
from .status import StatusResponse
from .exceptions import WorkerPoolError, WorkerPoolShuttingDownError, WorkerProvisionError
