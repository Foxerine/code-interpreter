"""
/files endpoints for sandbox file operations.
"""
from loguru import logger as l
from starlette.status import HTTP_201_CREATED

from gateway import meta_config
from gateway.fastapis.deps import WorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.files import (
    FileUploadRequest,
    FileUploadResponse,
)
from .export import router as export_router

router = TaggedAPIRouter(prefix="/files", tag="File operations")
router.include_router(export_router)


@router.post("", response_model=FileUploadResponse, status_code=HTTP_201_CREATED)
async def upload_files(request: FileUploadRequest, worker: WorkerDep) -> FileUploadResponse:
    """
    Upload files to the user's sandbox environment from presigned URLs.

    **Authentication**: Requires `user_uuid` query parameter to identify the session.

    **Request Body**:
    - `files`: List of file upload items, each containing:
      - `path`: Target directory path in sandbox (e.g., "/sandbox/data")
      - `name`: Target filename
      - `download_url`: Presigned URL to download the file from

    **Response** (201 Created):
    - `success`: Boolean indicating overall success
    - `results`: List of upload results with full_path and size

    **Error Responses**:
    - 413 Request Entity Too Large: File exceeds MAX_FILE_SIZE_MB limit
    - 400 Bad Request: Invalid path or path traversal attempt
    - 502 Bad Gateway: Failed to download from presigned URL
    """
    l.debug(f"Upload files request: {request}")
    max_size_bytes = meta_config.MAX_FILE_SIZE_MB * 1024 * 1024
    results = await worker.upload_files(request.files, max_size_bytes)
    l.debug(f"Upload files response: {results}")
    return FileUploadResponse(success=True, results=results)
