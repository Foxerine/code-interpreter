"""
SandboxFileSystem rich domain model for file operations.

This module provides the SandboxFileSystem class which encapsulates all
sandbox file operations including path validation, upload, and export.
"""
import asyncio
import os as sync_os
import uuid as uuid_mod
from collections.abc import AsyncGenerator, Callable, Coroutine
from pathlib import PurePosixPath
from typing import Any, ClassVar, TypeVar

import aiofiles
import aiohttp
from aiofiles import os as async_os
from loguru import logger as l
from ssrf_protect.ssrf_protect import SSRFProtect, SSRFProtectException

from gateway import meta_config
from gateway.utils.aiohttp_client_session_mixin import AioHttpClientSessionClassVarMixin

from .base import ModelBase
from .exceptions import BatchFileOperationError
from .field_types import Str256
from .files import (
    FileDownloadError,
    FileExportItem,
    FileExportResultItem,
    FileUploadItem,
    FileUploadResultItem,
    FileTooLargeError,
    SandboxFileRefBase,
)

# Type variables for generic file operation result aggregation
_FileItemT = TypeVar('_FileItemT', bound=SandboxFileRefBase)
_ResultT = TypeVar('_ResultT', FileUploadResultItem, FileExportResultItem)


class SandboxFileSystem(ModelBase, AioHttpClientSessionClassVarMixin):
    """
    Rich domain model for sandbox file system operations.

    Manages file uploads and exports with proper path validation and
    concurrency control. Follows the rich domain model pattern with
    properties directly held rather than using Config objects.

    The file_op_semaphore is passed in from WorkerPool to allow shared
    concurrency control across all workers.
    """
    # Constants
    SANDBOX_ROOT: ClassVar[str] = "/sandbox"
    CHUNK_SIZE: ClassVar[int] = 8192
    FILE_TRANSFER_TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(total=120.0, connect=10.0)

    # Properties (rich domain model - direct attributes)
    mount_point: Str256
    """Gateway-side mount point for direct sandbox access."""
    file_op_semaphore: asyncio.Semaphore
    """Shared semaphore for concurrency control (passed from WorkerPool)."""

    model_config = {'arbitrary_types_allowed': True}

    def compute_path(self, sandbox_path: str, filename: str) -> str:
        """
        Compute the mounted filesystem path for a sandbox file.

        Uses PurePosixPath.relative_to() for bulletproof path traversal prevention.
        This method resolves .. BEFORE validation, preventing normpath bypass attacks.

        Args:
            sandbox_path: Path in sandbox (e.g., /sandbox/data or /sandbox/data/file.txt).
                          If path already includes filename, it will be normalized.
            filename: Filename (e.g., input.csv).

        Returns:
            Full path in Gateway's mount point.

        Raises:
            ValueError: If path escapes sandbox boundary or contains invalid characters.
        """
        # Validate filename doesn't contain path separators
        if '/' in filename or '\\' in filename:
            raise ValueError("Invalid filename")

        # Use PurePosixPath for safe path handling
        sandbox_path_obj = PurePosixPath(sandbox_path)

        # Handle case where sandbox_path already includes the filename
        # e.g., path="/sandbox/file.txt", name="file.txt" -> extract dir "/sandbox"
        # This makes the API more robust against common caller mistakes
        if sandbox_path_obj.name == filename:
            sandbox_path_obj = sandbox_path_obj.parent
            l.debug(f"Auto-corrected path: extracted directory from full file path")

        # Use PurePosixPath for safe path validation
        # This handles all normalization internally and prevents traversal attacks
        sandbox_base = PurePosixPath(self.SANDBOX_ROOT)
        requested_dir = sandbox_path_obj
        full_path = requested_dir / filename

        # relative_to() raises ValueError if path escapes the base
        # This is the bulletproof check - works even after normalization
        try:
            relative = full_path.relative_to(sandbox_base)
        except ValueError:
            raise ValueError("Path escapes sandbox boundary")

        # Construct the final path in mount point
        return sync_os.path.join(self.mount_point, str(relative))

    async def upload_file(
        self,
        file_item: FileUploadItem,
        max_size_bytes: int,
    ) -> FileUploadResultItem:
        """
        Upload a single file to the sandbox via Gateway dual-mount.

        Downloads from the presigned URL and writes to the sandbox filesystem
        using atomic write (temp file + rename). Includes SSRF protection.

        Args:
            file_item: File upload item with path, name, and download URL.
            max_size_bytes: Maximum allowed file size in bytes.

        Returns:
            Upload result with full path and size.

        Raises:
            FileDownloadError: If SSRF protection blocks the URL.
            FileTooLargeError: If file exceeds size limit.
            aiohttp.ClientError: If download fails.
        """
        download_url = str(file_item.download_url)

        # SSRF protection
        if meta_config.SSRF_PROTECTION_ENABLED:
            try:
                SSRFProtect.validate(download_url)
            except SSRFProtectException as e:
                raise FileDownloadError(download_url, f"SSRF protection: {e}") from e

        target_path = self.compute_path(file_item.path, file_item.name)
        await async_os.makedirs(sync_os.path.dirname(target_path), exist_ok=True)

        tmp_path = f"{target_path}.{uuid_mod.uuid4().hex[:12]}.tmp"
        total_size = 0

        try:
            async with self.http_session.get(
                download_url,
                timeout=self.FILE_TRANSFER_TIMEOUT,
                allow_redirects=False,  # Prevent SSRF bypass via redirects
            ) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_size_bytes:
                    raise FileTooLargeError(int(content_length), max_size_bytes)

                async with aiofiles.open(tmp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                        total_size += len(chunk)
                        if total_size > max_size_bytes:
                            raise FileTooLargeError(total_size, max_size_bytes)
                        await f.write(chunk)

            await async_os.rename(tmp_path, target_path)
        except (FileTooLargeError, FileDownloadError, aiohttp.ClientError, OSError) as e:
            l.error(f"Upload failed: {type(e).__name__}: {e}")
            try:
                await async_os.remove(tmp_path)
                l.debug(f"Cleaned up temp file: {tmp_path}")
            except FileNotFoundError:
                l.debug(f"Temp file already removed: {tmp_path}")
            except OSError as cleanup_err:
                l.error(f"Failed to clean up temp file {tmp_path}: {cleanup_err}")
            raise

        l.debug(f"Uploaded file ({total_size} bytes)")
        return FileUploadResultItem(
            full_path=f"{file_item.path}/{file_item.name}",
            size=total_size,
        )

    async def export_file(self, file_item: FileExportItem) -> FileExportResultItem:
        """
        Export a single file from the sandbox via Gateway dual-mount.

        Reads from the sandbox filesystem and uploads to the presigned URL
        using streaming to avoid loading entire file into memory.

        Args:
            file_item: File export item with path, name, and upload URL.

        Returns:
            Export result with path, name, and size.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            PermissionError: If file cannot be read.
            aiohttp.ClientError: If upload fails.
        """
        source_path = self.compute_path(file_item.path, file_item.name)

        try:
            stat = await async_os.stat(source_path)
        except FileNotFoundError:
            l.error(f"Export failed: file not found: {file_item.path}/{file_item.name}")
            raise
        except PermissionError as e:
            l.error(f"Export failed: permission denied: {file_item.path}/{file_item.name}")
            raise

        async def file_reader() -> AsyncGenerator[bytes, None]:
            async with aiofiles.open(source_path, 'rb') as f:
                while chunk := await f.read(self.CHUNK_SIZE):
                    yield chunk

        try:
            async with self.http_session.put(
                str(file_item.upload_url),
                data=file_reader(),
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(stat.st_size),
                },
                timeout=self.FILE_TRANSFER_TIMEOUT,
            ) as response:
                response.raise_for_status()
        except aiohttp.ClientError as e:
            l.error(f"Export failed (upload): {type(e).__name__}: {e}")
            raise

        l.debug(f"Exported file ({stat.st_size} bytes)")
        return FileExportResultItem(
            path=file_item.path,
            name=file_item.name,
            size=stat.st_size,
        )

    async def _run_with_semaphore(
        self,
        func: Callable[[_FileItemT], Coroutine[Any, Any, _ResultT]],
        item: _FileItemT,
    ) -> _ResultT:
        """Run an async function with semaphore-based concurrency limiting."""
        async with self.file_op_semaphore:
            return await func(item)

    @staticmethod
    def _aggregate_results(
        file_items: list[_FileItemT],
        results: list[_ResultT | BaseException],
        operation_type: str,
    ) -> list[_ResultT]:
        """
        Aggregate file operation results, raising on any failures.

        Args:
            file_items: Original file items.
            results: Results or exceptions from asyncio.gather.
            operation_type: "Upload" or "Export" for error messages.

        Returns:
            List of successful results.

        Raises:
            BatchFileOperationError: If any operations failed.
        """
        successful: list[_ResultT] = []
        failed: list[tuple[_FileItemT, BaseException]] = []

        for file_item, result in zip(file_items, results, strict=True):
            if isinstance(result, BaseException):
                failed.append((file_item, result))
            else:
                successful.append(result)

        if failed:
            # Extract error type/message without exposing internal paths
            first_exc = failed[0][1]
            error_type = type(first_exc).__name__
            raise BatchFileOperationError(
                operation=operation_type,
                failed_count=len(failed),
                total_count=len(file_items),
                first_error=error_type,
            )

        return successful

    async def upload_files(
        self,
        files: list[FileUploadItem],
        max_size_bytes: int,
    ) -> list[FileUploadResultItem]:
        """
        Upload multiple files to the sandbox with concurrency control.

        Args:
            files: List of file upload items.
            max_size_bytes: Maximum allowed file size in bytes.

        Returns:
            List of upload results.

        Raises:
            BatchFileOperationError: If any uploads failed.
        """
        l.debug(f"Uploading {len(files)} file(s)")

        async def upload_one(file_item: FileUploadItem) -> FileUploadResultItem:
            return await self.upload_file(file_item, max_size_bytes)

        results = await asyncio.gather(
            *[self._run_with_semaphore(upload_one, f) for f in files],
            return_exceptions=True,
        )
        return self._aggregate_results(files, results, "Upload")

    async def export_files(self, files: list[FileExportItem]) -> list[FileExportResultItem]:
        """
        Export multiple files from the sandbox with concurrency control.

        Args:
            files: List of file export items.

        Returns:
            List of export results.

        Raises:
            BatchFileOperationError: If any exports failed.
        """
        l.debug(f"Exporting {len(files)} file(s)")

        results = await asyncio.gather(
            *[self._run_with_semaphore(self.export_file, f) for f in files],
            return_exceptions=True,
        )
        return self._aggregate_results(files, results, "Export")
