import asyncio
import time
import uuid
import os as sync_os  # Import the standard os module with an alias for clarity
from asyncio.subprocess import Process

import httpx
from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from fastapi import HTTPException
from loguru import logger as l
from aiofiles import os as async_os # Use aiofiles for async file operations

from dto import Worker, WorkerStatus


class WorkerManager:
    """
    Manages the lifecycle of Docker-based worker containers.

    This manager implements a "Virtual-Disk-per-Worker" architecture. It creates
    a fixed-size disk image file (.img) for each worker inside a single shared Docker
    volume. This .img file is then mapped into the worker container as a block device,
    which the worker mounts to provide a sandboxed, size-limited writable filesystem.
    """
    # --- Configuration variables (to be populated by init) ---
    WORKER_IMAGE_NAME: str
    INTERNAL_NETWORK_NAME: str
    MIN_IDLE_WORKERS: int
    MAX_TOTAL_WORKERS: int
    WORKER_IDLE_TIMEOUT: int
    RECYCLING_INTERVAL: int
    GATEWAY_INTERNAL_IP: str
    WORKER_MAX_DISK_SIZE_MB: int

    # --- Constants ---
    MAX_CREATION_RETRIES: int = 3
    CREATION_RETRY_DELAY: float = 1.0
    VDISKS_BASE_DIR: str = "/virtual_disks"  # The mount point for the shared 'virtual_disks' volume

    # --- Internal state and Locking Primitives ---
    docker: Docker = Docker()
    workers: dict[str, Worker] = {}
    user_to_worker_map: dict[str, str] = {}
    _idle_worker_ids: set[str] = set()
    _state_lock: asyncio.Lock = asyncio.Lock()
    _creation_semaphore: asyncio.Semaphore | None = None
    _is_initializing: bool = True
    _is_replenishing: bool = False
    _shutdown_event: asyncio.Event = asyncio.Event()

    @classmethod
    async def _run_subprocess(cls, cmd: list[str]) -> tuple[bytes, bytes]:
        """
        Asynchronously runs a shell command and raises an error on failure.
        This is a non-blocking replacement for subprocess.run(check=True).
        """
        process: Process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                f"Subprocess command '{' '.join(cmd)}' failed with exit code {process.returncode}.\n"
                f"Stderr: {stderr.decode(errors='ignore')}"
            )
        return stdout, stderr

    @classmethod
    async def init(
            cls,
            worker_image_name: str,
            internal_network_name: str,
            min_idle_workers: int,
            max_total_workers: int,
            worker_idle_timeout: int,
            recycling_interval: int,
            gateway_internal_ip: str,
            worker_max_disk_size_mb: int,
    ) -> None:
        """Initializes the WorkerManager, populating configuration and pre-warming the pool."""
        cls.WORKER_IMAGE_NAME = worker_image_name
        cls.INTERNAL_NETWORK_NAME = internal_network_name
        cls.MIN_IDLE_WORKERS = min_idle_workers
        cls.MAX_TOTAL_WORKERS = max_total_workers
        cls.WORKER_IDLE_TIMEOUT = worker_idle_timeout
        cls.RECYCLING_INTERVAL = recycling_interval
        cls.GATEWAY_INTERNAL_IP = gateway_internal_ip
        cls.WORKER_MAX_DISK_SIZE_MB = worker_max_disk_size_mb

        cls._creation_semaphore = asyncio.Semaphore(cls.MAX_TOTAL_WORKERS)
        cls._shutdown_event.clear()

        l.info("Initializing worker pool...")
        await async_os.makedirs(cls.VDISKS_BASE_DIR, exist_ok=True)

        try:
            # The volume name is determined by docker-compose: <project_name>_virtual_disks
            # We find it dynamically by assuming it's the one mounted to /virtual_disks.
            gateway_container = await cls.docker.containers.get(sync_os.environ['HOSTNAME'])
            gateway_mounts = (await gateway_container.show())['Mounts']

            vdisk_mount = next((m for m in gateway_mounts if m['Destination'] == cls.VDISKS_BASE_DIR), None)

            if not vdisk_mount or vdisk_mount.get('Type') != 'volume':
                raise RuntimeError(f"Could not find the named volume mount for {cls.VDISKS_BASE_DIR}")

            volume_name = vdisk_mount['Name']
            volume_info = await (await cls.docker.volumes.get(volume_name)).show()
            cls._volume_host_path = volume_info['Mountpoint']
            l.success(f"Discovered true host path for volume '{volume_name}': {cls._volume_host_path}")

        except (DockerError, KeyError, StopIteration, RuntimeError) as e:
            l.error(f"FATAL: Could not determine the true host path of the virtual_disks volume. Error: {e}")
            raise RuntimeError("Failed to initialize WorkerManager due to volume discovery failure.") from e

        await cls._cleanup_stale_workers()
        await cls._replenish_idle_pool()
        cls._is_initializing = False
        l.info(f"Worker pool initialized. Idle workers: {len(cls._idle_worker_ids)}")

    @classmethod
    async def close(cls) -> None:
        """Gracefully shuts down the WorkerManager, destroying all managed containers and volumes."""
        l.info("Shutting down WorkerManager...")
        cls._shutdown_event.set()

        async with cls._state_lock:
            all_workers = list(cls.workers.values())

        destroy_tasks = [cls._destroy_worker(worker) for worker in all_workers]
        await asyncio.gather(*destroy_tasks, return_exceptions=True)

        await cls.docker.close()
        l.info("WorkerManager shutdown complete.")

    @classmethod
    async def _cleanup_stale_workers(cls) -> None:
        """Removes any containers or virtual disk files left over from a previous unclean shutdown."""
        l.info("Cleaning up stale resources...")
        try:
            # Clean up stale containers
            old_containers = await cls.docker.containers.list(filters={"label": ["managed-by=code-interpreter-gateway"]})
            if old_containers:
                l.warning(f"Found {len(old_containers)} stale worker containers. Cleaning up...")
                cleanup_tasks = [c.delete(force=True) for c in old_containers]
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            # Clean up stale virtual disk files
            if await async_os.path.exists(cls.VDISKS_BASE_DIR):
                for filename in await async_os.listdir(cls.VDISKS_BASE_DIR):
                    if filename.endswith(".img"):
                        l.warning(f"Found stale virtual disk file: {filename}. Cleaning up...")
                        await async_os.remove(sync_os.path.join(cls.VDISKS_BASE_DIR, filename))

        except DockerError as e:
            l.error(f"Error during stale resource cleanup: {e}")

    @classmethod
    async def _create_new_worker(cls, retry_count: int = 0) -> Worker:
        if cls._shutdown_event.is_set():
            raise RuntimeError("WorkerManager is shutting down")
        # 移除了对 _is_initializing 的检查，因为 get_worker_for_user 会处理

        await cls._creation_semaphore.acquire()

        container_name = f"code-worker-{uuid.uuid4().hex[:12]}"
        # 始终使用容器内路径进行操作
        vdisk_container_path = sync_os.path.join(cls.VDISKS_BASE_DIR, f"{container_name}.img")

        container = None
        loop_device = None

        try:
            # 步骤 1: 创建稀疏文件
            l.info(f"Creating virtual disk: {vdisk_container_path}")
            await cls._run_subprocess(
                ["truncate", "-s", f"{cls.WORKER_MAX_DISK_SIZE_MB}M", vdisk_container_path]
            )

            # 步骤 2: 关联 loop 设备。现在它会因为 /dev 的实时同步而稳定成功。
            l.info(f"Associating {vdisk_container_path} with a loop device...")
            stdout, _ = await cls._run_subprocess(["losetup", "--find", "--show", vdisk_container_path])
            loop_device = stdout.decode().strip()
            if not loop_device:
                raise RuntimeError("losetup did not return a device path.")
            l.success(f"Associated disk for {container_name} with {loop_device}")

            # 步骤 3: 在 loop 设备上创建文件系统 (这是最标准的做法)
            l.info(f"Formatting loop device {loop_device}...")
            await cls._run_subprocess(["mkfs.ext4", "-F", loop_device])

            # 步骤 4: 创建并启动容器
            l.info(f"Creating worker container: {container_name}")
            device_mapping = [{"PathOnHost": loop_device, "PathInContainer": "/dev/vdisk", "CgroupPermissions": "rwm"}]

            container_config = {
                'Image': cls.WORKER_IMAGE_NAME,
                'Env': [f"GATEWAY_INTERNAL_IP={cls.GATEWAY_INTERNAL_IP}"],
                'HostConfig': {
                    'ReadonlyRootfs': True,
                    'NetworkMode': cls.INTERNAL_NETWORK_NAME,
                    'Memory': 1024 * 1024 * 1024,
                    'NanoCpus': 1_000_000_000,
                    'CapAdd': ['SYS_ADMIN', 'NET_ADMIN', 'NET_RAW'],
                    'SecurityOpt': ["apparmor:unconfined"],
                    'Devices': device_mapping,
                    'Tmpfs': {'/tmp': 'size=100m,exec', '/run': 'size=50m'},
                },
                'Labels': {'managed-by': "code-interpreter-gateway"},
            }
            container = await cls.docker.containers.create_or_replace(config=container_config, name=container_name)
            await container.start()

            worker = Worker(
                container_id=container.id, container_name=container_name,
                internal_url=f"http://{container_name}:8000",
                status=WorkerStatus.IDLE, loop_device=loop_device
            )

            if not await cls._is_worker_healthy(worker):
                raise RuntimeError("Worker failed health check after creation.")

            l.success(f"Worker {container_name} created and healthy.")
            return worker

        except Exception as e:
            # 回滚逻辑保持不变
            l.error(f"Failed to create worker {container_name} on attempt {retry_count+1}: {e}")
            if container:
                try: await container.delete(force=True)
                except Exception as ex: l.error(f"Rollback (container): {ex}")
            if loop_device:
                try: await cls._run_subprocess(["losetup", "-d", loop_device])
                except Exception as ex: l.debug(f"Rollback (losetup): {ex}")
            if await async_os.path.exists(vdisk_container_path):
                try: await async_os.remove(vdisk_container_path)
                except Exception as ex: l.error(f"Rollback (vdisk file): {ex}")

            cls._creation_semaphore.release()

            if retry_count < cls.MAX_CREATION_RETRIES:
                l.warning(f"Retrying worker creation ({retry_count + 1}/{cls.MAX_CREATION_RETRIES})...")
                await asyncio.sleep(cls.CREATION_RETRY_DELAY)
                return await cls._create_new_worker(retry_count + 1)
            else:
                raise RuntimeError("Failed to create worker after all retries") from e

    @classmethod
    async def _destroy_worker(cls, worker: Worker) -> None:
        """Destroys a worker container, its loop device, and its virtual disk file."""
        l.warning(f"Destroying worker: {worker.container_name}")
        vdisk_path = sync_os.path.join(cls.VDISKS_BASE_DIR, f"{worker.container_name}.img")

        try:
            container = cls.docker.containers.container(worker.container_id)
            await container.delete(force=True)
        except DockerError as e:
            if e.status != 404:
                l.error(f"Error deleting container {worker.container_name}: {e}")
        finally:
            # Always attempt to clean up the underlying infrastructure.

            # [NEW] Step 1: Detach the loop device.
            if worker.loop_device:
                try:
                    l.info(f"Detaching loop device {worker.loop_device} for {worker.container_name}")
                    await cls._run_subprocess(["losetup", "-d", worker.loop_device])
                except Exception as e:
                    l.error(f"Error detaching loop device for {worker.container_name}: {e}")

            # Step 2: Delete the virtual disk file.
            try:
                if await async_os.path.exists(vdisk_path):
                    await async_os.remove(vdisk_path)
                    l.info(f"Successfully destroyed virtual disk: {vdisk_path}")
            except Exception as e:
                l.error(f"Error during virtual disk cleanup for {worker.container_name}: {e}")

            cls._creation_semaphore.release()

    @classmethod
    async def get_worker_for_user(cls, user_uuid: str) -> Worker | None:
        """Gets an available worker for a user, allocating from the pool or creating a new one."""
        if cls._shutdown_event.is_set():
            raise HTTPException(status_code=503, detail="Service is shutting down")

        asyncio.create_task(cls._replenish_idle_pool())

        async with cls._state_lock:
            if user_uuid in cls.user_to_worker_map:
                worker_id = cls.user_to_worker_map[user_uuid]
                worker = cls.workers[worker_id]
                worker.last_active_timestamp = time.time()
                l.info(f"Reusing existing worker {worker.container_name} for user {user_uuid}")
                return worker

            if cls._idle_worker_ids:
                worker_id = cls._idle_worker_ids.pop()
                worker = cls.workers[worker_id]
                cls._bind_worker_to_user(worker, user_uuid)
                l.info(f"Assigned idle worker {worker.container_name} to user {user_uuid}")
                return worker

        l.info("No idle workers. Creating a new one synchronously for user request.")
        try:
            worker = await cls._create_new_worker()
            async with cls._state_lock:
                cls.workers[worker.container_id] = worker
                cls._bind_worker_to_user(worker, user_uuid)
            l.info(f"Assigned newly created worker {worker.container_name} to user {user_uuid}")
            return worker
        except Exception as e:
            l.error(f"Failed to create new worker for user request: {e}")
            raise HTTPException(status_code=503, detail="Could not provision a new worker environment at this time.")

    @classmethod
    async def release_worker_by_user(cls, user_uuid: str) -> None:
        """Releases a user's session and destroys the associated worker."""
        worker_to_destroy = None
        async with cls._state_lock:
            if user_uuid in cls.user_to_worker_map:
                container_id = cls.user_to_worker_map.pop(user_uuid)
                worker_to_destroy = cls.workers.pop(container_id, None)
                cls._idle_worker_ids.discard(container_id)

        if worker_to_destroy:
            l.info(f"Releasing worker {worker_to_destroy.container_name} from user {user_uuid}")
            await cls._destroy_worker(worker_to_destroy)
            asyncio.create_task(cls._replenish_idle_pool())
        else:
            l.warning(f"No active worker found for user {user_uuid} during release request.")

    @classmethod
    async def _replenish_idle_pool(cls) -> None:
        """Non-blocking task to ensure the idle pool has the minimum number of workers."""
        if cls._shutdown_event.is_set():
            return

        async with cls._state_lock:
            if cls._is_replenishing: return
            needed = cls.MIN_IDLE_WORKERS - len(cls._idle_worker_ids)
            if needed <= 0: return
            l.info(f"Replenishing idle pool. Need to create {needed} worker(s).")
            cls._is_replenishing = True

        try:
            tasks = [cls._create_new_worker() for _ in range(needed)]
            new_workers = await asyncio.gather(*tasks, return_exceptions=True)

            async with cls._state_lock:
                for worker in new_workers:
                    if isinstance(worker, Worker):
                        cls.workers[worker.container_id] = worker
                        cls._idle_worker_ids.add(worker.container_id)
                    else:
                        l.error(f"Failed to create worker during replenishment: {worker}")
        finally:
            async with cls._state_lock:
                cls._is_replenishing = False

    @classmethod
    def _bind_worker_to_user(cls, worker: Worker, user_uuid: str) -> None:
        """Internal helper to associate a worker with a user."""
        worker.status = WorkerStatus.BUSY
        worker.user_uuid = user_uuid
        worker.last_active_timestamp = time.time()
        cls.user_to_worker_map[user_uuid] = worker.container_id

    @classmethod
    async def _is_worker_healthy(cls, worker: Worker, timeout: int = 30) -> bool:
        """Performs a health check on a newly created worker."""
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                if cls._shutdown_event.is_set(): return False
                try:
                    response = await client.get(f"{worker.internal_url}/health", timeout=2.0)
                    if response.status_code == 200:
                        l.debug(f"Worker {worker.container_name} passed health check.")
                        return True
                except httpx.RequestError:
                    pass # Ignore connection errors while waiting for worker to start
                await asyncio.sleep(0.5)
        l.error(f"Worker {worker.container_name} failed health check after {timeout}s.")
        return False

    @classmethod
    async def recycle_timed_out_workers(cls) -> None:
        """Background task to find and destroy workers that have been idle for too long."""
        while not cls._shutdown_event.is_set():
            await asyncio.sleep(cls.RECYCLING_INTERVAL)
            try:
                workers_to_destroy = []
                async with cls._state_lock:
                    now = time.time()
                    # Check both busy and idle workers for timeout
                    for worker in list(cls.workers.values()):
                        if (now - worker.last_active_timestamp > cls.WORKER_IDLE_TIMEOUT):
                            l.warning(f"Worker {worker.container_name} timed out (idle for {now - worker.last_active_timestamp:.1f}s).")
                            workers_to_destroy.append(worker)

                    if not workers_to_destroy: continue

                    for worker in workers_to_destroy:
                        if worker.user_uuid:
                            cls.user_to_worker_map.pop(worker.user_uuid, None)
                        cls.workers.pop(worker.container_id, None)
                        cls._idle_worker_ids.discard(worker.container_id)

                if workers_to_destroy:
                    destroy_tasks = [cls._destroy_worker(w) for w in workers_to_destroy]
                    await asyncio.gather(*destroy_tasks, return_exceptions=True)
                    asyncio.create_task(cls._replenish_idle_pool())

            except asyncio.CancelledError:
                l.info("Idle worker recycling task cancelled.")
                break
            except Exception as e:
                l.error(f"Error in recycle_timed_out_workers: {e}")
