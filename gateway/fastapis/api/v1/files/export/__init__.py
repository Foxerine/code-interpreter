"""
/files/export endpoint for exporting files from sandbox.
"""
from loguru import logger as l

from gateway.fastapis.deps import ExistingWorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.files import (
    FileExportRequest,
    FileExportResponse,
)

router = TaggedAPIRouter(prefix="/export", tag="File operations")


@router.post("", response_model=FileExportResponse)
async def export_files(request: FileExportRequest, worker: ExistingWorkerDep) -> FileExportResponse:
    """Export files from sandbox to presigned URLs."""
    l.debug(f"Export files request: {request}")
    results = await worker.export_files(request.files)
    l.debug(f"Export files response: {results}")
    return FileExportResponse(success=True, results=results)
