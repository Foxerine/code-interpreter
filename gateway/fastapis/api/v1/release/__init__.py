"""
/release endpoint.
"""
from uuid import UUID

from loguru import logger as l
from starlette.status import HTTP_204_NO_CONTENT

from gateway.fastapis.deps import ExistingWorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter

router = TaggedAPIRouter(prefix="/release", tag="Release session")


@router.post("", status_code=HTTP_204_NO_CONTENT)
async def release(user_uuid: UUID, worker: ExistingWorkerDep) -> None:
    l.debug(f"Release request for user: {user_uuid}")
    await worker.release()
    l.info(f"Released worker for user {user_uuid}")
