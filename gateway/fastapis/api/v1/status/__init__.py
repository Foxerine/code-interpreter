"""
/status endpoint.
"""
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.status import StatusResponse
from gateway.models.worker import WorkerPool

router = TaggedAPIRouter(prefix="/status", tag="Status")


@router.get("", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    return StatusResponse(
        total_workers=len(WorkerPool.workers),
        busy_workers=len(WorkerPool.user_to_worker_map),
        is_initializing=WorkerPool.is_initializing,
    )
