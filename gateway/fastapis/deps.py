"""
Global FastAPI dependencies.
"""
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header

from gateway import meta_config
from gateway.models.exceptions import WorkerPoolShuttingDownError, WorkerProvisionError
from gateway.models.worker import Worker, WorkerPool
from gateway.utils.http_exceptions import raise_not_found, raise_service_unavailable, raise_unauthorized


async def verify_token(x_auth_token: str = Header()) -> None:
    if not secrets.compare_digest(x_auth_token, meta_config.AUTH_TOKEN):
        raise_unauthorized("Invalid or missing authentication token")


async def get_worker(user_uuid: UUID) -> Worker:
    """Dependency to get or create a worker for a user."""
    try:
        worker = await WorkerPool.get_worker_for_user(user_uuid)
        if worker is None:
            raise_service_unavailable("Failed to get worker")
        return worker
    except WorkerPoolShuttingDownError as e:
        raise_service_unavailable(e.message)
    except WorkerProvisionError as e:
        raise_service_unavailable(e.message)


async def get_existing_worker(user_uuid: UUID) -> Worker:
    """Dependency to get existing worker for a user (no creation)."""
    worker = WorkerPool.get_worker_by_user(user_uuid)
    if worker is None:
        raise_not_found("No active session found for user")
    return worker


VerifyTokenDep = Annotated[None, Depends(verify_token)]
WorkerDep = Annotated[Worker, Depends(get_worker)]
ExistingWorkerDep = Annotated[Worker, Depends(get_existing_worker)]
