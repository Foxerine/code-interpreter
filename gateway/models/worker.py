"""
Worker and WorkerPool rich domain models.
"""
import asyncio
import os as sync_os
import time
from asyncio.subprocess import Process
from enum import StrEnum
from typing import ClassVar
from uuid import UUID
import uuid as uuid_mod

import aiohttp
from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from aiofiles import os as async_os
from loguru import logger as l
from pydantic import Field, PrivateAttr

from gateway import meta_config
from gateway.utils.aiohttp_client_session_mixin import AioHttpClientSessionClassVarMixin
from .base import ModelBase
from .exceptions import WorkerPoolShuttingDownError, WorkerProvisionError
from .field_types import Str64, Str128, Str256
from .files import (
    FileExportItem,
    FileExportResultItem,
    FileRef,
    FileUploadItem,
    FileUploadResultItem,
    SandboxFile,
)


class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    CREATING = "creating"
    ERROR = "error"


class WorkerExecuteResultData(ModelBase):
    """Data from worker execution response."""
    result_text: str | None = None
    result_base64: str | None = None


class WorkerExecuteResult(ModelBase):
    """Result from worker execution."""
    status_code: int
    data: WorkerExecuteResultData | None = None
    text: str


class Worker(ModelBase, AioHttpClientSessionClassVarMixin):
    """
    Rich domain model for a Worker container.

    Worker knows how to manage its own lifecycle including health checks,
    binding to users, and self-destruction.

    Inherits AioHttpClientSessionClassVarMixin for shared HTTP session.
    """
    # Reusable timeout for health checks
    _HEALTH_CHECK_TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(total=2.0)

    container_id: Str128
    container_name: Str128
    internal_url: Str256
    status: WorkerStatus = WorkerStatus.CREATING
    loop_device: Str64
    """Loop device path (e.g., /dev/loop10)"""
    user_uuid: UUID | None = None
    last_active_timestamp: float = Field(default_factory=time.time)

    async def health_check(self, timeout: int = 30) -> bool:
        """Performs health check on this worker."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # TODO: Move sleep interval (0.5) to meta_config
                async with self.http_session.get(
                    f"{self.internal_url}/api/v1/kernel/health",
                    timeout=self._HEALTH_CHECK_TIMEOUT,
                ) as response:
                    if response.status == 200:
                        l.debug(f"Worker {self.container_name} passed health check.")
                        return True
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(0.5)
        l.error(f"Worker {self.container_name} failed health check after {timeout}s.")
        return False

    async def destroy(self, docker: Docker) -> None:
        """Destroys this worker container and its resources."""
        l.warning(f"Destroying worker: {self.container_name}")
        vdisk_path = sync_os.path.join(WorkerPool.VDISKS_BASE_DIR, f"{self.container_name}.img")

        try:
            container = docker.containers.container(self.container_id)
            await container.delete(force=True)
        except DockerError as e:
            if e.status != 404:
                l.error(f"Error deleting container {self.container_name}: {e}")
        finally:
            if self.loop_device and self.loop_device.strip():
                try:
                    l.info(f"Detaching loop device {self.loop_device} for {self.container_name}")
                    await WorkerPool._run_subprocess(["losetup", "-d", self.loop_device])
                except Exception as e:
                    l.error(f"Error detaching loop device for {self.container_name}: {e}")

            try:
                if await async_os.path.exists(vdisk_path):
                    await async_os.remove(vdisk_path)
                    l.info(f"Successfully destroyed virtual disk: {vdisk_path}")
            except Exception as e:
                l.error(f"Error during virtual disk cleanup for {self.container_name}: {e}")

    def bind_to_user(self, user_uuid: UUID) -> None:
        """Binds this worker to a user."""
        self.status = WorkerStatus.BUSY
        self.user_uuid = user_uuid
        self.last_active_timestamp = time.time()

    def touch(self) -> None:
        """Updates last active timestamp."""
        self.last_active_timestamp = time.time()

    async def release(self) -> None:
        """Releases this worker by destroying it and replenishing the pool."""
        await WorkerPool.release_worker(self)

    def is_timed_out(self, timeout: int) -> bool:
        """Checks if this worker has been idle too long."""
        return time.time() - self.last_active_timestamp > timeout

    @property
    def container(self) -> DockerContainer:
        """Gets the Docker container for this worker."""
        return WorkerPool.docker.containers.container(self.container_id)

    async def execute(self, code: str, timeout: float) -> WorkerExecuteResult:
        """Executes code in this worker and returns the result."""
        l.debug(f"Executing code on worker {self.container_name}")
        self.touch()

        async with self.http_session.post(
            f"{self.internal_url}/api/v1/kernel/execute",
            json={"code": code},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            text = await response.text()
            l.debug(f"Worker response: status={response.status}, body={text}")

            data = None
            if response.status == 200:
                json_data = await response.json()
                data = WorkerExecuteResultData(
                    result_text=json_data["result_text"],
                    result_base64=json_data["result_base64"],
                )

            return WorkerExecuteResult(
                status_code=response.status,
                data=data,
                text=text,
            )

    async def upload_files(self, files: list[FileUploadItem], max_size_bytes: int) -> list[FileUploadResultItem]:
        """Uploads files to this worker's sandbox."""

        async def upload_one(file_item: FileUploadItem) -> FileUploadResultItem:
            sandbox_file = await SandboxFile.from_url(
                directory=file_item.path,
                filename=file_item.name,
                download_url=str(file_item.download_url),
                max_size_bytes=max_size_bytes,
            )
            result = await sandbox_file.write_to_container(self.container)
            return FileUploadResultItem(full_path=result['full_path'], size=result['size'])

        return list(await asyncio.gather(*[upload_one(f) for f in files]))

    async def export_files(self, files: list[FileExportItem]) -> list[FileExportResultItem]:
        """Exports files from this worker's sandbox."""

        async def export_one(file_item: FileExportItem) -> FileExportResultItem:
            sandbox_file = await SandboxFile.read_from_container(
                container=self.container,
                directory=file_item.path,
                filename=file_item.name,
            )
            await sandbox_file.upload_to_url(str(file_item.upload_url))
            return FileExportResultItem(path=file_item.path, name=file_item.name, size=sandbox_file.size)

        return list(await asyncio.gather(*[export_one(f) for f in files]))

    async def delete_files(self, files: list[FileRef]) -> None:
        """Deletes files from this worker's sandbox."""

        async def delete_one(file_ref: FileRef) -> None:
            await SandboxFile.delete_from_container(
                container=self.container,
                directory=file_ref.path,
                filename=file_ref.name,
            )

        await asyncio.gather(*[delete_one(f) for f in files])


class WorkerPool:
    """
    Rich domain model for managing Worker collection.

    Implements the "Virtual-Disk-per-Worker" architecture where each worker
    gets a fixed-size disk image file.

    This class uses classmethod pattern and should never be instantiated.
    """
    # Configuration (set during init)
    WORKER_IMAGE_NAME: ClassVar[str]
    INTERNAL_NETWORK_NAME: ClassVar[str]
    MIN_IDLE_WORKERS: ClassVar[int]
    MAX_TOTAL_WORKERS: ClassVar[int]
    WORKER_IDLE_TIMEOUT: ClassVar[int]
    RECYCLING_INTERVAL: ClassVar[int]
    GATEWAY_INTERNAL_IP: ClassVar[str]
    WORKER_MAX_DISK_SIZE_MB: ClassVar[int]
    WORKER_CPU: ClassVar[float]
    WORKER_RAM_MB: ClassVar[int]

    # Constants
    MAX_CREATION_RETRIES: ClassVar[int] = 3
    CREATION_RETRY_DELAY: ClassVar[float] = 1.0
    VDISKS_BASE_DIR: ClassVar[str] = "/virtual_disks"

    # State
    _docker: ClassVar[Docker | None] = None
    _workers: ClassVar[dict[str, Worker]] = {}
    _user_to_worker_map: ClassVar[dict[UUID, str]] = {}
    _idle_worker_ids: ClassVar[set[str]] = set()
    _state_lock: ClassVar[asyncio.Lock | None] = None
    _creation_semaphore: ClassVar[asyncio.Semaphore | None] = None
    _is_initializing: ClassVar[bool] = True
    _is_replenishing: ClassVar[bool] = False
    _shutdown_event: ClassVar[asyncio.Event | None] = None
    _volume_host_path: ClassVar[str] = ""

    def __new__(cls, *args, **kwargs) -> "WorkerPool":
        raise RuntimeError(f"{cls.__name__} is a pure classmethod singleton, cannot be instantiated")

    @classmethod
    async def _run_subprocess(cls, cmd: list[str]) -> tuple[bytes, bytes]:
        """Runs a shell command asynchronously."""
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
    async def init(cls) -> None:
        """Initializes the WorkerPool from meta_config."""
        cls.WORKER_IMAGE_NAME = meta_config.WORKER_IMAGE_NAME
        cls.INTERNAL_NETWORK_NAME = meta_config.INTERNAL_NETWORK_NAME
        cls.MIN_IDLE_WORKERS = meta_config.MIN_IDLE_WORKERS
        cls.MAX_TOTAL_WORKERS = meta_config.MAX_TOTAL_WORKERS
        cls.WORKER_IDLE_TIMEOUT = meta_config.WORKER_IDLE_TIMEOUT
        cls.RECYCLING_INTERVAL = meta_config.RECYCLING_INTERVAL
        cls.GATEWAY_INTERNAL_IP = meta_config.GATEWAY_INTERNAL_IP
        cls.WORKER_MAX_DISK_SIZE_MB = meta_config.WORKER_MAX_DISK_SIZE_MB
        cls.WORKER_CPU = meta_config.WORKER_CPU
        cls.WORKER_RAM_MB = meta_config.WORKER_RAM_MB

        cls._docker = Docker()
        cls._workers = {}
        cls._user_to_worker_map = {}
        cls._idle_worker_ids = set()
        cls._state_lock = asyncio.Lock()
        cls._creation_semaphore = asyncio.Semaphore(cls.MAX_TOTAL_WORKERS)
        cls._shutdown_event = asyncio.Event()
        cls._shutdown_event.clear()

        l.info("Initializing worker pool...")
        await async_os.makedirs(cls.VDISKS_BASE_DIR, exist_ok=True)

        try:
            gateway_container = await cls._docker.containers.get(sync_os.environ['HOSTNAME'])
            gateway_mounts = (await gateway_container.show())['Mounts']

            vdisk_mount = next((m for m in gateway_mounts if m['Destination'] == cls.VDISKS_BASE_DIR), None)
            if not vdisk_mount or vdisk_mount.get('Type') != 'volume':
                raise RuntimeError(f"Could not find the named volume mount for {cls.VDISKS_BASE_DIR}")

            volume_name = vdisk_mount['Name']
            volume_info = await (await cls._docker.volumes.get(volume_name)).show()
            cls._volume_host_path = volume_info['Mountpoint']
            l.success(f"Discovered true host path for volume '{volume_name}': {cls._volume_host_path}")
        except (DockerError, KeyError, StopIteration, RuntimeError) as e:
            l.error(f"FATAL: Could not determine the true host path of the virtual_disks volume. Error: {e}")
            raise RuntimeError("Failed to initialize WorkerPool due to volume discovery failure.") from e

        await cls._cleanup_stale_workers()
        await cls._replenish_idle_pool()
        cls._is_initializing = False
        l.info(f"Worker pool initialized. Idle workers: {len(cls._idle_worker_ids)}")

    @classmethod
    async def close(cls) -> None:
        """Shuts down the WorkerPool gracefully."""
        l.info("Shutting down WorkerPool...")
        if cls._shutdown_event:
            cls._shutdown_event.set()

        async with cls._state_lock:
            all_workers = list(cls._workers.values())

        destroy_tasks = [cls._destroy_worker(worker) for worker in all_workers]
        await asyncio.gather(*destroy_tasks, return_exceptions=True)

        if cls._docker:
            await cls._docker.close()
        l.info("WorkerPool shutdown complete.")

    @classmethod
    async def _cleanup_stale_workers(cls) -> None:
        """Removes stale containers and disk files from previous runs."""
        l.info("Cleaning up stale resources...")
        try:
            old_containers = await cls._docker.containers.list(filters={"label": ["managed-by=code-interpreter-gateway"]})
            if old_containers:
                l.warning(f"Found {len(old_containers)} stale worker containers. Cleaning up...")
                cleanup_tasks = [c.delete(force=True) for c in old_containers]
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            if await async_os.path.exists(cls.VDISKS_BASE_DIR):
                for filename in await async_os.listdir(cls.VDISKS_BASE_DIR):
                    if filename.endswith(".img"):
                        l.warning(f"Found stale virtual disk file: {filename}. Cleaning up...")
                        await async_os.remove(sync_os.path.join(cls.VDISKS_BASE_DIR, filename))
        except DockerError as e:
            l.error(f"Error during stale resource cleanup: {e}")

    @classmethod
    async def _create_worker(cls, retry_count: int = 0) -> Worker:
        """Creates a new worker container with virtual disk."""
        if cls._shutdown_event and cls._shutdown_event.is_set():
            raise RuntimeError("WorkerPool is shutting down")

        await cls._creation_semaphore.acquire()

        container_name = f"code-worker-{uuid_mod.uuid4().hex[:12]}"
        vdisk_container_path = sync_os.path.join(cls.VDISKS_BASE_DIR, f"{container_name}.img")

        container = None
        loop_device = None

        try:
            l.info(f"Creating virtual disk: {vdisk_container_path}")
            await cls._run_subprocess(
                ["truncate", "-s", f"{cls.WORKER_MAX_DISK_SIZE_MB}M", vdisk_container_path]
            )

            l.info(f"Associating {vdisk_container_path} with a loop device...")
            stdout, _ = await cls._run_subprocess(["losetup", "--find", "--show", vdisk_container_path])
            loop_device = stdout.decode().strip()
            if not loop_device or not loop_device.startswith("/dev/loop"):
                raise RuntimeError(f"Invalid loop device path returned: {loop_device!r}")
            l.success(f"Associated disk for {container_name} with {loop_device}")

            l.info(f"Formatting loop device {loop_device}...")
            await cls._run_subprocess(["mkfs.ext4", "-F", loop_device])

            l.info(f"Creating worker container: {container_name}")
            device_mapping = [{"PathOnHost": loop_device, "PathInContainer": "/dev/vdisk", "CgroupPermissions": "rwm"}]

            container_config = {
                'Image': cls.WORKER_IMAGE_NAME,
                'Env': [f"GATEWAY_INTERNAL_IP={cls.GATEWAY_INTERNAL_IP}"],
                'HostConfig': {
                    'ReadonlyRootfs': True,
                    'NetworkMode': cls.INTERNAL_NETWORK_NAME,
                    'Memory': cls.WORKER_RAM_MB * 1024 * 1024,
                    'NanoCpus': int(cls.WORKER_CPU * 1_000_000_000),
                    'CapAdd': ['SYS_ADMIN', 'NET_ADMIN', 'NET_RAW'],
                    'SecurityOpt': ["apparmor:unconfined"],
                    'Devices': device_mapping,
                    'Tmpfs': {'/tmp': 'size=100m,exec', '/run': 'size=50m'},
                },
                'Labels': {'managed-by': "code-interpreter-gateway"},
            }
            container = await cls._docker.containers.create_or_replace(config=container_config, name=container_name)
            await container.start()

            worker = Worker(
                container_id=container.id,
                container_name=container_name,
                internal_url=f"http://{container_name}:8000",
                status=WorkerStatus.IDLE,
                loop_device=loop_device,
            )

            if not await worker.health_check():
                raise RuntimeError("Worker failed health check after creation.")

            l.success(f"Worker {container_name} created and healthy.")
            return worker

        except Exception as e:
            l.error(f"Failed to create worker {container_name} on attempt {retry_count + 1}: {e}")
            if container:
                try:
                    await container.delete(force=True)
                except Exception as ex:
                    l.error(f"Rollback (container): {ex}")
            if loop_device:
                try:
                    await cls._run_subprocess(["losetup", "-d", loop_device])
                except Exception as ex:
                    l.debug(f"Rollback (losetup): {ex}")
            if await async_os.path.exists(vdisk_container_path):
                try:
                    await async_os.remove(vdisk_container_path)
                except Exception as ex:
                    l.error(f"Rollback (vdisk file): {ex}")

            cls._creation_semaphore.release()

            if retry_count < cls.MAX_CREATION_RETRIES:
                l.warning(f"Retrying worker creation ({retry_count + 1}/{cls.MAX_CREATION_RETRIES})...")
                await asyncio.sleep(cls.CREATION_RETRY_DELAY)
                return await cls._create_worker(retry_count + 1)
            else:
                raise RuntimeError("Failed to create worker after all retries") from e

    @classmethod
    async def _destroy_worker(cls, worker: Worker) -> None:
        """Destroys a worker and releases its semaphore slot."""
        await worker.destroy(cls._docker)
        cls._creation_semaphore.release()

    @classmethod
    async def get_worker_for_user(cls, user_uuid: UUID) -> Worker | None:
        """Gets or assigns a worker for a user."""
        if cls._shutdown_event and cls._shutdown_event.is_set():
            raise WorkerPoolShuttingDownError()

        asyncio.create_task(cls._replenish_idle_pool())

        async with cls._state_lock:
            if user_uuid in cls._user_to_worker_map:
                worker_id = cls._user_to_worker_map[user_uuid]
                worker = cls._workers[worker_id]
                worker.touch()
                l.info(f"Reusing existing worker {worker.container_name} for user {user_uuid}")
                return worker

            if cls._idle_worker_ids:
                worker_id = cls._idle_worker_ids.pop()
                worker = cls._workers[worker_id]
                worker.bind_to_user(user_uuid)
                cls._user_to_worker_map[user_uuid] = worker.container_id
                l.info(f"Assigned idle worker {worker.container_name} to user {user_uuid}")
                return worker

        l.info("No idle workers. Creating a new one synchronously for user request.")
        worker = None
        try:
            worker = await cls._create_worker()
            async with cls._state_lock:
                cls._workers[worker.container_id] = worker
                worker.bind_to_user(user_uuid)
                cls._user_to_worker_map[user_uuid] = worker.container_id
            l.info(f"Assigned newly created worker {worker.container_name} to user {user_uuid}")
            return worker
        except Exception as e:
            l.error(f"Failed to create new worker for user request: {e}")
            if worker is not None:
                await cls._destroy_worker(worker)
            raise WorkerProvisionError("Could not provision a new worker environment at this time.") from e

    @classmethod
    async def release_worker_by_user(cls, user_uuid: UUID) -> None:
        """Releases a user's worker session."""
        worker_to_destroy = None
        async with cls._state_lock:
            if user_uuid in cls._user_to_worker_map:
                container_id = cls._user_to_worker_map.pop(user_uuid)
                worker_to_destroy = cls._workers.pop(container_id, None)
                cls._idle_worker_ids.discard(container_id)

        if worker_to_destroy:
            l.info(f"Releasing worker {worker_to_destroy.container_name} from user {user_uuid}")
            await cls._destroy_worker(worker_to_destroy)
            asyncio.create_task(cls._replenish_idle_pool())
        else:
            l.warning(f"No active worker found for user {user_uuid} during release request.")

    @classmethod
    async def release_worker(cls, worker: "Worker") -> None:
        """Releases a specific worker instance."""
        async with cls._state_lock:
            if worker.user_uuid:
                cls._user_to_worker_map.pop(worker.user_uuid, None)
            cls._workers.pop(worker.container_id, None)
            cls._idle_worker_ids.discard(worker.container_id)

        l.info(f"Releasing worker {worker.container_name}")
        await cls._destroy_worker(worker)
        asyncio.create_task(cls._replenish_idle_pool())

    @classmethod
    async def _replenish_idle_pool(cls) -> None:
        """Ensures minimum idle workers are available."""
        if cls._shutdown_event and cls._shutdown_event.is_set():
            return

        async with cls._state_lock:
            if cls._is_replenishing:
                return
            needed = cls.MIN_IDLE_WORKERS - len(cls._idle_worker_ids)
            if needed <= 0:
                return
            l.info(f"Replenishing idle pool. Need to create {needed} worker(s).")
            cls._is_replenishing = True

        try:
            tasks = [cls._create_worker() for _ in range(needed)]
            new_workers = await asyncio.gather(*tasks, return_exceptions=True)

            async with cls._state_lock:
                for worker in new_workers:
                    if isinstance(worker, Worker):
                        cls._workers[worker.container_id] = worker
                        cls._idle_worker_ids.add(worker.container_id)
                    else:
                        l.error(f"Failed to create worker during replenishment: {worker}")
        finally:
            async with cls._state_lock:
                cls._is_replenishing = False

    @classmethod
    def get_worker_by_id(cls, worker_id: str) -> Worker | None:
        return cls._workers.get(worker_id)

    @classmethod
    def get_worker_by_user(cls, user_uuid: UUID) -> Worker | None:
        container_id = cls._user_to_worker_map.get(user_uuid)
        if container_id:
            return cls._workers.get(container_id)
        return None

    @classmethod
    async def recycle_timed_out_workers(cls) -> None:
        """Background task to destroy timed out workers."""
        while not (cls._shutdown_event and cls._shutdown_event.is_set()):
            await asyncio.sleep(cls.RECYCLING_INTERVAL)
            try:
                workers_to_destroy: list[Worker] = []
                async with cls._state_lock:
                    for worker in list(cls._workers.values()):
                        if worker.is_timed_out(cls.WORKER_IDLE_TIMEOUT):
                            l.warning(f"Worker {worker.container_name} timed out.")
                            workers_to_destroy.append(worker)

                    if not workers_to_destroy:
                        continue

                    for worker in workers_to_destroy:
                        if worker.user_uuid:
                            cls._user_to_worker_map.pop(worker.user_uuid, None)
                        cls._workers.pop(worker.container_id, None)
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

    @classmethod
    @property
    def workers(cls) -> dict[str, Worker]:
        return cls._workers

    @classmethod
    @property
    def user_to_worker_map(cls) -> dict[UUID, str]:
        return cls._user_to_worker_map

    @classmethod
    @property
    def is_initializing(cls) -> bool:
        return cls._is_initializing

    @classmethod
    @property
    def docker(cls) -> Docker:
        assert cls._docker is not None
        return cls._docker
