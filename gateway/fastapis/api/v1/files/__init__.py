"""
/files endpoints for sandbox file operations.
"""
from loguru import logger as l
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from gateway import meta_config
from gateway.fastapis.deps import ExistingWorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.files import (
    FileDeleteRequest,
    FileUploadRequest,
    FileUploadResponse,
)
from .export import router as export_router

router = TaggedAPIRouter(prefix="/files", tag="File operations")
router.include_router(export_router)


@router.post("", response_model=FileUploadResponse, status_code=HTTP_201_CREATED)
async def upload_files(request: FileUploadRequest, worker: ExistingWorkerDep) -> FileUploadResponse:
    """Upload files to sandbox from presigned URLs."""
    l.debug(f"Upload files request: {request}")
    max_size_bytes = meta_config.MAX_FILE_SIZE_MB * 1024 * 1024
    results = await worker.upload_files(request.files, max_size_bytes)
    l.debug(f"Upload files response: {results}")
    return FileUploadResponse(success=True, results=results)


@router.delete("", status_code=HTTP_204_NO_CONTENT)
async def delete_files(request: FileDeleteRequest, worker: ExistingWorkerDep) -> None:
    """Delete files from sandbox."""
    l.debug(f"Delete files request: {request}")
    await worker.delete_files(request.files)
    l.debug(f"Deleted {len(request.files)} files from sandbox")
