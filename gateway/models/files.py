"""
File handling models for sandbox file operations via Docker API.
"""
import io
import tarfile
import tempfile
from pathlib import PurePosixPath
from typing import ClassVar

import aiohttp
from aiodocker.containers import DockerContainer
from loguru import logger as l
from pydantic import AnyHttpUrl, Field, PrivateAttr, model_validator
from ssrf_protect.ssrf_protect import SSRFProtect, SSRFProtectException

from gateway import meta_config
from gateway.utils.aiohttp_client_session_mixin import AioHttpClientSessionClassVarMixin
from .base import ModelBase
from .field_types import SandboxPathStr, SandboxFileName, NonNegativeInt, Str1280


# =============================================================================
# Exceptions
# =============================================================================

class FileOperationError(Exception):
    pass


class PathSecurityError(FileOperationError):
    def __init__(self, path: str, reason: str = "Path traversal detected"):
        self.path = path
        self.message = f"{reason}: {path}"
        super().__init__(self.message)


class FileTooLargeError(FileOperationError):
    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size
        self.message = f"File size ({size} bytes) exceeds limit ({max_size} bytes)"
        super().__init__(self.message)


class FileDownloadError(FileOperationError):
    def __init__(self, url: str, reason: str):
        self.url = url[:100] + "..." if len(url) > 100 else url
        self.message = f"Failed to download file: {reason}"
        super().__init__(self.message)


# =============================================================================
# Rich Domain Models
# =============================================================================

class SandboxPath(ModelBase):
    """Validated path within the sandbox boundary."""
    SANDBOX_BASE: ClassVar[str] = "/sandbox"

    directory: str
    filename: str
    _full_path: str = PrivateAttr()

    @model_validator(mode='after')
    def validate_and_normalize(self) -> "SandboxPath":
        self._full_path = self._compute_full_path()
        return self

    def _compute_full_path(self) -> str:
        # Use pathlib for safe path normalization
        base = PurePosixPath(self.SANDBOX_BASE)
        dir_path = PurePosixPath(self.directory)
        full = dir_path / self.filename

        # Normalize using pathlib (handles .. and .)
        # Since PurePosixPath doesn't resolve against filesystem, we normalize manually
        try:
            # Join with base and check if result is still under base
            normalized = (base / full.relative_to("/")).as_posix()
        except ValueError:
            normalized = full.as_posix()

        # Ensure result stays within sandbox
        normalized_path = PurePosixPath(normalized)
        try:
            normalized_path.relative_to(self.SANDBOX_BASE)
        except ValueError:
            raise PathSecurityError(normalized, f"Path must be within {self.SANDBOX_BASE}")

        return normalized

    @property
    def full_path(self) -> str:
        return self._full_path

    @property
    def dir_path(self) -> str:
        return self.directory if self.directory.endswith("/") else self.directory + "/"

    def __str__(self) -> str:
        return self._full_path


class SandboxFile(ModelBase, AioHttpClientSessionClassVarMixin):
    """Rich domain model for sandbox file operations.

    Inherits AioHttpClientSessionClassVarMixin for shared HTTP session.
    """
    # Reusable timeout objects to avoid repeated instantiation
    _DOWNLOAD_TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(total=60.0)
    _UPLOAD_TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(total=120.0)

    path: SandboxPath
    content: bytes | None = None
    size: int = 0

    @model_validator(mode='after')
    def update_size(self) -> "SandboxFile":
        if self.content is not None:
            self.size = len(self.content)
        return self

    @classmethod
    async def from_url(
        cls,
        directory: str,
        filename: str,
        download_url: str,
        max_size_bytes: int,
    ) -> "SandboxFile":
        path = SandboxPath(directory=directory, filename=filename)
        content = await cls._download_from_url(download_url, max_size_bytes)
        return cls(path=path, content=content, size=len(content))

    @classmethod
    async def _download_from_url(cls, url: str, max_size_bytes: int) -> bytes:
        if meta_config.SSRF_PROTECTION_ENABLED:
            try:
                SSRFProtect().clean_url(url)
            except SSRFProtectException as e:
                raise FileDownloadError(url, f"SSRF protection: {e}") from e

        try:
            # TODO: Move timeout and spooled file max_size (10MB) to meta_config
            async with cls.get_http_session().get(
                url,
                timeout=cls._DOWNLOAD_TIMEOUT,
            ) as response:
                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_size_bytes:
                    raise FileTooLargeError(int(content_length), max_size_bytes)

                with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode='w+b') as tmp:
                    total_size = 0
                    async for chunk in response.content.iter_chunked(8192):
                        total_size += len(chunk)
                        if total_size > max_size_bytes:
                            raise FileTooLargeError(total_size, max_size_bytes)
                        tmp.write(chunk)
                    tmp.seek(0)
                    return tmp.read()
        except aiohttp.ClientResponseError as e:
            raise FileDownloadError(url, f"HTTP {e.status}") from e
        except aiohttp.ClientError as e:
            raise FileDownloadError(url, str(e)) from e

    def to_tar_archive(self) -> bytes:
        if self.content is None:
            raise ValueError("Cannot create archive: file has no content")

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            file_info = tarfile.TarInfo(name=self.path.filename)
            file_info.size = len(self.content)
            tar.addfile(file_info, io.BytesIO(self.content))
        tar_buffer.seek(0)
        return tar_buffer.read()

    @classmethod
    def extract_from_tar(cls, tar_data: bytes, filename: str) -> bytes:
        tar_buffer = io.BytesIO(tar_data)
        with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
            # Use data_filter (Python 3.12+) for safe extraction
            for member in tar.getmembers(filter="data"):
                if member.name == filename or member.name.endswith("/" + filename):
                    f = tar.extractfile(member)
                    if f:
                        return f.read()
            raise FileNotFoundError(f"File '{filename}' not found in archive")

    async def write_to_container(self, container: DockerContainer) -> dict[str, bool | str | int]:
        if self.content is None:
            raise ValueError("Cannot write: file has no content")

        tar_data = self.to_tar_archive()
        l.info(f"Writing file to container: {self.path.full_path} ({self.size} bytes)")
        await container.put_archive(self.path.dir_path, tar_data)
        return {"success": True, "full_path": self.path.full_path, "size": self.size}

    @classmethod
    async def read_from_container(
        cls,
        container: DockerContainer,
        directory: str,
        filename: str,
    ) -> "SandboxFile":
        path = SandboxPath(directory=directory, filename=filename)
        l.info(f"Reading file from container: {path.full_path}")

        tar_stream = await container.get_archive(path.full_path)
        chunks: list[bytes] = []
        async for chunk in tar_stream:
            chunks.append(chunk)
        tar_data = b"".join(chunks)
        content = cls.extract_from_tar(tar_data, filename)
        return cls(path=path, content=content, size=len(content))

    @classmethod
    async def delete_from_container(
        cls,
        container: DockerContainer,
        directory: str,
        filename: str,
    ) -> bool:
        path = SandboxPath(directory=directory, filename=filename)
        l.info(f"Deleting file from container: {path.full_path}")

        exec_result = await container.exec(
            cmd=["rm", "-f", "--", path.full_path],
            stdout=True,
            stderr=True,
        )
        async with exec_result.start() as stream:
            await stream.read_out()
        return True

    async def upload_to_url(self, upload_url: str) -> None:
        if self.content is None:
            raise ValueError("Cannot upload: file has no content")

        l.info(f"Uploading file to OSS: {self.path.full_path} ({self.size} bytes)")
        try:
            # TODO: Move timeout to meta_config
            async with self.http_session.put(
                upload_url,
                data=self.content,
                headers={"Content-Type": "application/octet-stream"},
                timeout=self._UPLOAD_TIMEOUT,
            ) as response:
                response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            raise FileOperationError(f"Failed to upload file: HTTP {e.status}") from e
        except aiohttp.ClientError as e:
            raise FileOperationError(f"Failed to upload file: {e}") from e


# =============================================================================
# Request/Response Models (following inheritance conventions)
# =============================================================================

class SandboxFileRefBase(ModelBase):
    """Base class for sandbox file references."""
    path: SandboxPathStr
    """Directory path in sandbox"""
    name: SandboxFileName
    """Filename"""


class FileResultBase(ModelBase):
    """Base class for file operation results."""
    size: NonNegativeInt
    """File size in bytes"""


class FileUploadItem(SandboxFileRefBase):
    download_url: AnyHttpUrl
    """Presigned URL to download from"""


class FileUploadRequest(ModelBase):
    files: list[FileUploadItem] = Field(min_length=1, max_length=100)


class FileUploadResultItem(FileResultBase):
    full_path: Str1280
    """Full path in sandbox"""


class FileUploadResponse(ModelBase):
    success: bool = True
    results: list[FileUploadResultItem]


class FileExportItem(SandboxFileRefBase):
    upload_url: AnyHttpUrl
    """Presigned URL to upload to"""


class FileExportRequest(ModelBase):
    files: list[FileExportItem] = Field(min_length=1, max_length=100)


class FileExportResultItem(SandboxFileRefBase, FileResultBase):
    """Export result inherits both file reference and result base."""
    pass


class FileExportResponse(ModelBase):
    success: bool = True
    results: list[FileExportResultItem]


class FileRef(SandboxFileRefBase):
    pass


class FileDeleteRequest(ModelBase):
    files: list[FileRef] = Field(min_length=1, max_length=100)
