import asyncio
import time
import uuid

import httpx
from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from fastapi import HTTPException
from loguru import logger as l

from dto import Worker, WorkerStatus


class WorkerManager:
    """
    Manages the lifecycle of Docker-based worker containers.

    This class is implemented as a Singleton using only class-level variables
    and methods. It handles the creation, assignment, and destruction of
    workers, maintaining a pool of idle workers to handle user requests
    promptly.
    """
    # --- Configuration variables ---
    # These must be set by calling the `init` method before use.
    WORKER_IMAGE_NAME: str
    INTERNAL_NETWORK_NAME: str
    MIN_IDLE_WORKERS: int
    MAX_TOTAL_WORKERS: int
    WORKER_IDLE_TIMEOUT: int
    RECYCLING_INTERVAL: int

    # --- Internal state ---
    docker: Docker = Docker()
    workers: dict[str, Worker] = {}  # container_id -> Worker
    user_to_worker_map: dict[str, str] = {}  # user_uuid -> container_id
    idle_workers: asyncio.Queue[Worker] = asyncio.Queue()
    _lock: asyncio.Lock = asyncio.Lock()
    _is_initializing: bool = True

    @classmethod
    async def init(
        cls,
        worker_image_name: str,
        internal_network_name: str,
        min_idle_workers: int,
        max_total_workers: int,
        worker_idle_timeout: int,
        recycling_interval: int,
    ) -> None:
        """
        Injects configuration and initializes the worker pool.

        Cleans up any stale worker containers from previous runs and
        pre-warms the pool by creating a minimum number of idle workers.
        """
        # 1. Configure the manager
        cls.WORKER_IMAGE_NAME = worker_image_name
        cls.INTERNAL_NETWORK_NAME = internal_network_name
        cls.MIN_IDLE_WORKERS = min_idle_workers
        cls.MAX_TOTAL_WORKERS = max_total_workers
        cls.WORKER_IDLE_TIMEOUT = worker_idle_timeout
        cls.RECYCLING_INTERVAL = recycling_interval

        # 2. Initialize the pool
        l.info("Initializing worker pool...")
        await cls._cleanup_stale_workers()
        await cls._replenish_idle_pool()
        cls._is_initializing = False
        l.info(f"Worker pool initialized. Idle workers: {cls.idle_workers.qsize()}")

    @classmethod
    async def close(cls) -> None:
        """Closes the Docker client connection."""
        await cls.docker.close()

    @classmethod
    async def _cleanup_stale_workers(cls) -> None:
        """Finds and removes any dangling worker containers managed by this gateway."""
        try:
            old_workers: list[DockerContainer] = await cls.docker.containers.list(
                filters={"label": [f"managed-by=code-interpreter-gateway"]},
            )
            if not old_workers:
                return

            l.warning(f"Found {len(old_workers)} stale worker containers. Cleaning up...")
            cleanup_tasks = [container.delete(force=True) for container in old_workers]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            l.info("Stale worker cleanup complete.")
        except DockerError as e:
            l.error(f"Error during stale worker cleanup: {e}")

    @classmethod
    async def _create_new_worker(cls) -> Worker:
        """
        Creates, starts, and health-checks a single new worker container.

        :return: A healthy Worker object or None if creation fails.
        """
        container_name = f"code-worker-{uuid.uuid4().hex[:12]}"
        try:
            l.info(f"Creating new worker container: {container_name}")
            container: DockerContainer = await cls.docker.containers.create_or_replace(
                config={
                    'Image': cls.WORKER_IMAGE_NAME,
                    'HostConfig': {
                        'NetworkMode': cls.INTERNAL_NETWORK_NAME,
                    },
                    'Labels': {'managed-by': "code-interpreter-gateway"},
                },
                name=container_name,
            )
            await container.start()

            worker = Worker(
                container_id=container.id,
                container_name=container_name,
                internal_url=f"http://{container_name}:8000",
                status=WorkerStatus.IDLE,
            )

            is_healthy = await cls._is_worker_healthy(worker)
            if not is_healthy:
                l.error(f"Newly created worker {container_name} is unhealthy. Removing.")
                await cls._destroy_worker(worker)
                raise RuntimeError("Worker failed health check after creation.")

            l.success(f"Worker {container_name} created and healthy.")
            return worker
        except DockerError as e:
            msg = f"Failed to create container {container_name}: {e}"
            l.error(msg)
            raise RuntimeError(msg)

    @classmethod
    async def _is_worker_healthy(cls, worker: Worker, timeout: int = 30) -> bool:
        """
        Performs a health check on a worker by polling its /health endpoint.

        :param worker: The worker to check.
        :param timeout: The maximum time in seconds to wait for the worker to become healthy.
        :return: True if the worker is healthy, False otherwise.
        """
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                try:
                    response = await client.get(f"{worker.internal_url}/health", timeout=2.0)
                    if response.status_code == 200:
                        return True
                except httpx.RequestError:
                    await asyncio.sleep(0.1)
            return False

    @classmethod
    async def _destroy_worker(cls, worker: Worker) -> None:
        """
        Stops and removes a worker's Docker container and cleans up internal state.

        :param worker: The worker to destroy.
        """
        l.warning(f"Destroying worker: {worker.container_name}")
        try:
            container: DockerContainer = cls.docker.containers.container(worker.container_id)
            await container.delete(force=True)
        except DockerError as e:
            if e.status == 404:
                l.warning(f"Worker {worker.container_name} not found.")
            else:
                msg = f"Error deleting container {worker.container_name}: {e}"
                l.error(msg)
                raise RuntimeError(msg)
        finally:
            # Clean up internal state
            cls.workers.pop(worker.container_id, None)
            if worker.user_uuid and worker.user_uuid in cls.user_to_worker_map:
                cls.user_to_worker_map.pop(worker.user_uuid, None)

    @classmethod
    async def get_worker_for_user(cls, user_uuid: str) -> Worker:
        """
        Gets a worker for a given user.

        Retrieves an existing worker, an idle worker from the pool, or creates
        a new one.

        :param user_uuid: The UUID of the user requesting a worker.
        :return: An available Worker instance.
        :raises HTTPException: If the pool is initializing or no worker is available.
        """
        async with cls._lock:
            if cls._is_initializing:
                raise HTTPException(
                    status_code=503,
                    detail="Worker pool is initializing. Please try again shortly.",
                )

            # Case 1: User already has an active worker
            if user_uuid in cls.user_to_worker_map:
                container_id = cls.user_to_worker_map[user_uuid]
                worker = cls.workers[container_id]
                worker.last_active_timestamp = time.time()
                l.info(f"Found existing worker {worker.container_name} for user {user_uuid}")
                return worker

            # Case 2: Get an idle worker from the pool
            if not cls.idle_workers.empty():
                worker = await cls.idle_workers.get()
                cls._bind_worker_to_user(worker, user_uuid)
                l.info(f"Assigned idle worker {worker.container_name} to user {user_uuid}")
                return worker

            # Case 3: Create a new worker if under the configured maximum limit
            if len(cls.workers) < cls.MAX_TOTAL_WORKERS:
                l.info("No idle workers available. Attempting to create a new one.")
                worker = await cls._create_new_worker()
                if worker:
                    cls.workers[worker.container_id] = worker
                    cls._bind_worker_to_user(worker, user_uuid)
                    l.info(
                        f"Assigned newly created worker {worker.container_name} to user {user_uuid}"
                    )
                    return worker

            # Case 4: Max limit reached, no workers available
            raise HTTPException(status_code=503, detail="No available workers. Please try again later.")

    @classmethod
    def _bind_worker_to_user(cls, worker: Worker, user_uuid: str) -> None:
        """
        Assigns a worker to a user and updates its state.

        :param worker: The worker to be assigned.
        :param user_uuid: The user's UUID.
        """
        worker.status = WorkerStatus.BUSY
        worker.user_uuid = user_uuid
        worker.last_active_timestamp = time.time()
        cls.user_to_worker_map[user_uuid] = worker.container_id

    @classmethod
    async def release_worker_by_user(cls, user_uuid: str) -> None:
        """
        Releases a worker previously assigned to a user.

        This method destroys the worker container and triggers pool replenishment.

        :param user_uuid: The UUID of the user releasing the worker.
        """
        async with cls._lock:
            if user_uuid not in cls.user_to_worker_map:
                return

            container_id = cls.user_to_worker_map.pop(user_uuid)
            worker = cls.workers.pop(container_id)
            l.info(f"User {user_uuid} released worker {worker.container_name}. Destroying...")
            await cls._destroy_worker(worker)
            await cls._replenish_idle_pool()

    @classmethod
    async def _replenish_idle_pool(cls) -> None:
        """
        Creates new workers to meet the minimum idle worker requirement.

        This function should always be called within a lock to ensure thread safety.
        """
        needed_count = cls.MIN_IDLE_WORKERS - cls.idle_workers.qsize()
        available_slots = cls.MAX_TOTAL_WORKERS - len(cls.workers)

        creation_count = min(needed_count, available_slots)
        if creation_count <= 0:
            return

        l.info(f"Replenishing idle pool. Need to create {creation_count} worker(s).")
        tasks = [cls._create_new_worker() for _ in range(creation_count)]
        new_workers = await asyncio.gather(*tasks)

        for worker in new_workers:
            if worker:
                cls.workers[worker.container_id] = worker
                await cls.idle_workers.put(worker)

    @classmethod
    async def recycle_timed_out_workers(cls) -> None:
        """
        Periodically checks for and recycles workers that have been idle for too long.

        This method is designed to be run as a continuous background task.
        """
        while True:
            await asyncio.sleep(cls.RECYCLING_INTERVAL)
            async with cls._lock:
                l.info("Running background task to recycle timed-out workers...")
                now = time.time()
                timed_out_users: list[str] = []
                for user_uuid, container_id in cls.user_to_worker_map.items():
                    worker = cls.workers.get(container_id)
                    if worker and (now - worker.last_active_timestamp > cls.WORKER_IDLE_TIMEOUT):
                        timed_out_users.append(user_uuid)

                if timed_out_users:
                    l.warning(f"Found {len(timed_out_users)} timed-out workers to recycle.")
                    for user_uuid in timed_out_users:
                        container_id = cls.user_to_worker_map.pop(user_uuid)
                        worker = cls.workers.pop(container_id)
                        await cls._destroy_worker(worker)

                    await cls._replenish_idle_pool()
                else:
                    l.info("No timed-out workers found.")
