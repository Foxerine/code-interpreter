"""
/files/export endpoint for exporting files from sandbox.
"""
from loguru import logger as l

from gateway.fastapis.deps import WorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.files import (
    FileExportRequest,
    FileExportResponse,
)

router = TaggedAPIRouter(prefix="/export", tag="File operations")


@router.post("", response_model=FileExportResponse)
async def export_files(request: FileExportRequest, worker: WorkerDep) -> FileExportResponse:
    """
    Export files from the user's sandbox environment to presigned URLs.

    **Authentication**: Requires `user_uuid` query parameter to identify the session.

    **Request Body**:
    - `files`: List of file export items, each containing:
      - `path`: Source directory path in sandbox (e.g., "/sandbox/output")
      - `name`: Source filename to export
      - `upload_url`: Presigned URL to upload the file to

    **Response** (200 OK):
    - `success`: Boolean indicating overall success
    - `results`: List of export results with path, name, and size

    **Error Responses**:
    - 404 Not Found: File does not exist in sandbox
    - 400 Bad Request: Invalid path or path traversal attempt
    - 502 Bad Gateway: Failed to upload to presigned URL
    """
    l.debug(f"Export files request: {request}")
    results = await worker.export_files(request.files)
    l.debug(f"Export files response: {results}")
    return FileExportResponse(success=True, results=results)
