"""
/status endpoint.
"""
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.status import StatusResponse
from gateway.models.worker import WorkerPool

router = TaggedAPIRouter(prefix="/status", tag="Status")


@router.get("", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """
    Get the current status of the Code Interpreter Gateway.

    **Authentication**: None required (public endpoint).

    **Response** (200 OK):
    - `total_workers`: Total number of worker containers (busy + idle)
    - `busy_workers`: Number of workers currently assigned to users
    - `is_initializing`: True if the pool is still starting up

    **Notes**:
    - Useful for health checks and capacity monitoring
    - `is_initializing=True` indicates the pool is not yet ready for requests
    """
    return StatusResponse(
        total_workers=len(WorkerPool.get_workers()),
        busy_workers=len(WorkerPool.get_user_to_worker_map()),
        is_initializing=WorkerPool.get_is_initializing(),
    )
