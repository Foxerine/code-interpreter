"""
/health endpoint.
"""
from worker.fastapis.tagged_api_router import TaggedAPIRouter
from worker.models import HealthResponse, JupyterKernel
from worker.utils.http_exceptions import raise_service_unavailable

router = TaggedAPIRouter(prefix="/health", tag="Health check")


@router.get("", response_model=HealthResponse)
async def get_health_status() -> HealthResponse:
    if await JupyterKernel.is_healthy():
        return HealthResponse(status="ok")
    raise_service_unavailable("Kernel is not healthy")
