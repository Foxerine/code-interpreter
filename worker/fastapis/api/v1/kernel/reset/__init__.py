"""
/reset endpoint.
"""
from starlette.status import HTTP_204_NO_CONTENT

from worker.fastapis.tagged_api_router import TaggedAPIRouter
from worker.models import JupyterKernel
from worker.utils.http_exceptions import raise_internal_error

router = TaggedAPIRouter(prefix="/reset", tag="Reset kernel")


@router.post("", status_code=HTTP_204_NO_CONTENT)
async def reset_kernel() -> None:
    if not await JupyterKernel.reset():
        raise_internal_error("Failed to reset Python kernel.")
