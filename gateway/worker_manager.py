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
    Manages the lifecycle of Docker-based worker containers using a sophisticated
    locking strategy for high concurrency and safety.
    """
    # --- Configuration variables ---
    WORKER_IMAGE_NAME: str
    INTERNAL_NETWORK_NAME: str
    MIN_IDLE_WORKERS: int
    MAX_TOTAL_WORKERS: int
    WORKER_IDLE_TIMEOUT: int
    RECYCLING_INTERVAL: int
    MAX_CREATION_RETRIES: int = 3  # 新增：创建重试次数
    CREATION_RETRY_DELAY: float = 1.0  # 新增：重试延迟

    # --- Internal state and Locking Primitives ---
    docker: Docker = Docker()
    workers: dict[str, Worker] = {}
    user_to_worker_map: dict[str, str] = {}

    # 改进：使用计数器而不是 Queue，避免线程安全问题
    _idle_worker_ids: set[str] = set()  # 存储空闲容器 ID

    _state_lock: asyncio.Lock = asyncio.Lock()
    _creation_semaphore: asyncio.Semaphore | None = None

    _is_initializing: bool = True
    _is_replenishing: bool = False
    _shutdown_event: asyncio.Event = asyncio.Event()  # 新增：优雅关闭信号

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
        cls.WORKER_IMAGE_NAME = worker_image_name
        cls.INTERNAL_NETWORK_NAME = internal_network_name
        cls.MIN_IDLE_WORKERS = min_idle_workers
        cls.MAX_TOTAL_WORKERS = max_total_workers
        cls.WORKER_IDLE_TIMEOUT = worker_idle_timeout
        cls.RECYCLING_INTERVAL = recycling_interval

        cls._creation_semaphore = asyncio.Semaphore(cls.MAX_TOTAL_WORKERS)
        cls._shutdown_event.clear()

        l.info("Initializing worker pool...")
        await cls._cleanup_stale_workers()
        await cls._replenish_idle_pool()
        cls._is_initializing = False

        async with cls._state_lock:
            idle_count = len(cls._idle_worker_ids)
        l.info(f"Worker pool initialized. Idle workers: {idle_count}")

    @classmethod
    async def close(cls) -> None:
        """优雅关闭"""
        l.info("Shutting down WorkerManager...")
        cls._shutdown_event.set()

        async with cls._state_lock:
            all_container_ids = list(cls.workers.keys())

        # 并发删除所有容器
        destroy_tasks = [
            cls._destroy_worker(cls.workers[cid])
            for cid in all_container_ids
            if cid in cls.workers
        ]
        await asyncio.gather(*destroy_tasks, return_exceptions=True)

        await cls.docker.close()
        l.info("WorkerManager shutdown complete.")

    @classmethod
    async def _cleanup_stale_workers(cls) -> None:
        """清理遗留容器，增强错误处理"""
        try:
            old_workers = await cls.docker.containers.list(
                filters={"label": [f"managed-by=code-interpreter-gateway"]},
            )
            if not old_workers:
                return

            l.warning(f"Found {len(old_workers)} stale worker containers. Cleaning up...")

            # 并发删除，收集结果
            cleanup_tasks = [
                cls._safe_delete_container(container)
                for container in old_workers
            ]
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            # 统计成功/失败数量
            success_count = sum(1 for r in results if r is True)
            failure_count = len(results) - success_count

            l.info(f"Stale worker cleanup: {success_count} succeeded, {failure_count} failed.")
        except DockerError as e:
            l.error(f"Error during stale worker cleanup: {e}")

    @classmethod
    async def _safe_delete_container(cls, container: DockerContainer) -> bool:
        """安全删除容器并释放信号量"""
        try:
            await container.delete(force=True)
            try:
                cls._creation_semaphore.release()
            except ValueError:
                pass  # 已经释放到最大值
            return True
        except DockerError as e:
            if e.status != 404:  # 404 表示容器已不存在
                l.error(f"Failed to delete container {container.id[:12]}: {e}")
            return False

    @classmethod
    async def _create_new_worker(cls, retry_count: int = 0) -> Worker:
        """
        创建新容器，带重试机制
        """
        if cls._shutdown_event.is_set():
            raise RuntimeError("WorkerManager is shutting down")

        l.debug(f"Attempting to acquire creation permit (attempt {retry_count + 1})...")
        await cls._creation_semaphore.acquire()
        l.debug("Creation permit acquired.")

        container_name = f"code-worker-{uuid.uuid4().hex[:12]}"
        container = None

        try:
            l.info(f"Creating new worker container: {container_name}")
            container = await cls.docker.containers.create_or_replace(
                config={
                    'Image': cls.WORKER_IMAGE_NAME,
                    'HostConfig': {
                        'NetworkMode': cls.INTERNAL_NETWORK_NAME,
                        # 新增：资源限制
                        'Memory': 1024 * 1024 * 1024,  # 512MB
                        'CpuShares': 1024,
                    },
                    'Labels': {
                        'managed-by': "code-interpreter-gateway",
                        'created-at': str(int(time.time())),
                    },
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

            if not await cls._is_worker_healthy(worker):
                raise RuntimeError("Worker failed health check after creation.")

            l.success(f"Worker {container_name} created and healthy.")
            return worker

        except Exception as e:
            l.error(f"Failed to create worker {container_name}: {e}")

            # 清理失败的容器
            if container:
                try:
                    await container.delete(force=True)
                except Exception as cleanup_error:
                    l.error(f"Failed to cleanup failed container: {cleanup_error}")

            # 释放信号量
            cls._creation_semaphore.release()
            l.debug("Creation permit released due to error.")

            # 重试逻辑
            if retry_count < cls.MAX_CREATION_RETRIES:
                l.warning(f"Retrying worker creation ({retry_count + 1}/{cls.MAX_CREATION_RETRIES})...")
                await asyncio.sleep(cls.CREATION_RETRY_DELAY * (retry_count + 1))
                return await cls._create_new_worker(retry_count + 1)
            else:
                raise RuntimeError(f"Failed to create worker after {cls.MAX_CREATION_RETRIES} retries") from e

    @classmethod
    async def _destroy_worker(cls, worker: Worker) -> None:
        """销毁容器，增强错误处理"""
        l.warning(f"Destroying worker: {worker.container_name}")
        try:
            container = cls.docker.containers.container(worker.container_id)
            await container.delete(force=True)
            l.info(f"Worker {worker.container_name} destroyed successfully.")
        except DockerError as e:
            if e.status != 404:
                l.error(f"Error deleting container {worker.container_name}: {e}")
        finally:
            cls._creation_semaphore.release()
            l.debug(f"Creation permit released for destroyed worker {worker.container_name}")

    @classmethod
    async def get_worker_for_user(cls, user_uuid: str) -> Worker:
        """
        为用户获取容器，改进版本
        """
        if cls._shutdown_event.is_set():
            raise HTTPException(status_code=503, detail="Service is shutting down")

        # 触发后台补充（非阻塞）
        cls._trigger_background_replenishment()

        async with cls._state_lock:
            if cls._is_initializing:
                raise HTTPException(
                    status_code=503,
                    detail="Worker pool is initializing. Please try again shortly."
                )

            # 1. 检查用户是否已有容器
            if user_uuid in cls.user_to_worker_map:
                worker = cls.workers[cls.user_to_worker_map[user_uuid]]
                worker.last_active_timestamp = time.time()
                l.info(f"Reusing existing worker {worker.container_name} for user {user_uuid}")
                return worker

            # 2. 尝试从空闲池获取
            if cls._idle_worker_ids:
                worker_id = cls._idle_worker_ids.pop()
                worker = cls.workers[worker_id]
                cls._bind_worker_to_user(worker, user_uuid)
                l.info(f"Assigned idle worker {worker.container_name} to user {user_uuid}")
                return worker

        # 3. 池子为空，同步创建新容器（在锁外）
        l.info("No idle workers available. Creating a new one synchronously.")
        try:
            worker = await cls._create_new_worker()
            async with cls._state_lock:
                cls.workers[worker.container_id] = worker
                cls._bind_worker_to_user(worker, user_uuid)
            l.info(f"Assigned newly created worker {worker.container_name} to user {user_uuid}")
            return worker
        except Exception as e:
            l.error(f"Failed to create worker for user request: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Could not create a new worker: {str(e)}"
            )

    @classmethod
    async def release_worker_by_user(cls, user_uuid: str) -> None:
        """
        释放用户的容器
        """
        worker_to_destroy = None
        async with cls._state_lock:
            if user_uuid in cls.user_to_worker_map:
                container_id = cls.user_to_worker_map.pop(user_uuid)
                worker_to_destroy = cls.workers.pop(container_id, None)
                # 从空闲集合中移除（如果存在）
                cls._idle_worker_ids.discard(container_id)

        if worker_to_destroy:
            l.info(f"Releasing worker {worker_to_destroy.container_name} from user {user_uuid}")
            await cls._destroy_worker(worker_to_destroy)
            cls._trigger_background_replenishment()
        else:
            l.warning(f"No worker found for user {user_uuid} during release")

    @classmethod
    def _trigger_background_replenishment(cls):
        """触发后台补充，非阻塞"""
        if not cls._shutdown_event.is_set():
            asyncio.create_task(cls._replenish_idle_pool())

    @classmethod
    async def _replenish_idle_pool(cls) -> None:
        """
        补充空闲池，改进版本
        """
        if cls._shutdown_event.is_set():
            return

        async with cls._state_lock:
            if cls._is_replenishing:
                return

            needed_count = cls.MIN_IDLE_WORKERS - len(cls._idle_worker_ids)
            if needed_count <= 0:
                return

            l.info(f"Replenishing idle pool. Need to add {needed_count} worker(s).")
            cls._is_replenishing = True

        # 在锁外并发创建
        tasks = [cls._create_new_worker() for _ in range(needed_count)]
        new_workers = await asyncio.gather(*tasks, return_exceptions=True)

        async with cls._state_lock:
            successful_creations = 0
            for worker in new_workers:
                if isinstance(worker, Worker):
                    cls.workers[worker.container_id] = worker
                    cls._idle_worker_ids.add(worker.container_id)
                    successful_creations += 1
                elif isinstance(worker, Exception):
                    l.error(f"Failed to create worker during replenishment: {worker}")

            if successful_creations > 0:
                l.info(f"Successfully added {successful_creations}/{needed_count} worker(s) to idle pool.")
            else:
                l.error("Failed to add any workers to idle pool!")

            cls._is_replenishing = False

    @classmethod
    def _bind_worker_to_user(cls, worker: Worker, user_uuid: str) -> None:
        """绑定容器到用户"""
        worker.status = WorkerStatus.BUSY
        worker.user_uuid = user_uuid
        worker.last_active_timestamp = time.time()
        cls.user_to_worker_map[user_uuid] = worker.container_id

    @classmethod
    async def _is_worker_healthy(cls, worker: Worker, timeout: int = 30) -> bool:
        """
        健康检查，改进版本
        """
        start_time = time.time()
        retry_interval = 0.5  # 增加重试间隔，减少请求频率

        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                if cls._shutdown_event.is_set():
                    return False

                try:
                    response = await client.get(
                        f"{worker.internal_url}/health",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        l.debug(f"Worker {worker.container_name} passed health check")
                        return True
                except httpx.RequestError as e:
                    l.debug(f"Health check failed for {worker.container_name}: {e}")

                await asyncio.sleep(retry_interval)

            l.error(f"Worker {worker.container_name} failed health check after {timeout}s")
            return False

    @classmethod
    async def recycle_timed_out_workers(cls) -> None:
        """
        回收超时容器，后台任务
        """
        while not cls._shutdown_event.is_set():
            try:
                await asyncio.sleep(cls.RECYCLING_INTERVAL)

                workers_to_destroy = []
                async with cls._state_lock:
                    l.info("Running background task to recycle timed-out workers...")
                    now = time.time()

                    for user_uuid, container_id in list(cls.user_to_worker_map.items()):
                        worker = cls.workers.get(container_id)
                        if worker and (now - worker.last_active_timestamp > cls.WORKER_IDLE_TIMEOUT):
                            l.warning(
                                f"Worker {worker.container_name} for user {user_uuid} "
                                f"timed out (idle for {now - worker.last_active_timestamp:.1f}s)."
                            )
                            cls.user_to_worker_map.pop(user_uuid)
                            worker_to_destroy = cls.workers.pop(container_id)
                            cls._idle_worker_ids.discard(container_id)
                            workers_to_destroy.append(worker_to_destroy)

                # 在锁外删除容器
                if workers_to_destroy:
                    l.info(f"Destroying {len(workers_to_destroy)} timed-out worker(s)...")
                    destroy_tasks = [
                        cls._destroy_worker(worker)
                        for worker in workers_to_destroy
                    ]
                    await asyncio.gather(*destroy_tasks, return_exceptions=True)
                    cls._trigger_background_replenishment()
                else:
                    l.info("No timed-out workers found.")

            except Exception as e:
                l.error(f"Error in recycle_timed_out_workers: {e}")
                # 继续运行，不要因为单次错误而停止

    @classmethod
    async def get_pool_stats(cls) -> dict:
        """
        获取池子统计信息（用于监控）
        """
        async with cls._state_lock:
            return {
                "total_workers": len(cls.workers),
                "idle_workers": len(cls._idle_worker_ids),
                "busy_workers": len(cls.user_to_worker_map),
                "is_replenishing": cls._is_replenishing,
                "is_initializing": cls._is_initializing,
                "available_capacity": cls._creation_semaphore._value,
            }

