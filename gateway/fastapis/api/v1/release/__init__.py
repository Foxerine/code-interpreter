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
    """
    Release a user's sandbox session and return the worker to the idle pool.

    **Authentication**: Requires `user_uuid` query parameter to identify the session.

    **Response** (204 No Content): Session released successfully.

    **Error Responses**:
    - 404 Not Found: No active session found for the given user_uuid

    **Notes**:
    - The sandbox environment is destroyed and cannot be recovered
    - Any unsaved data in the sandbox will be lost
    - A new session will be created on the next request
    """
    l.debug(f"Release request for user: {user_uuid}")
    await worker.release()
    l.info(f"Released worker for user {user_uuid}")
