"""
VirtualDisk rich domain model for lifecycle management.

This module provides the VirtualDisk class which encapsulates all virtual disk
operations including creation, mounting, and destruction. It implements the
"Single Source of Truth" pattern where destroy() is the only cleanup code path.
"""
import os as sync_os
import re

from aiofiles import os as async_os
from loguru import logger as l

from gateway.utils.subprocess import run_cmd

from .base import ModelBase
from .field_types import Str64, Str128, Str256


class VirtualDisk(ModelBase):
    """
    Rich domain model for virtual disk lifecycle management.

    Manages the complete lifecycle of a virtual disk: create → attach_loop →
    format → mount_to_host → destroy. The destroy() method is the single
    source of truth for cleanup, eliminating code duplication.

    Attributes follow the rich domain model pattern - directly held properties
    rather than a separate Config object.
    """
    container_name: Str128
    """Name of the worker container this disk belongs to."""
    vdisks_base_dir: Str256
    """Base directory for virtual disk image files (e.g., /virtual_disks)."""
    worker_mounts_dir: Str256
    """Directory for Gateway-side mount points (e.g., /worker_mounts)."""
    size_mb: int
    """Size of the virtual disk in megabytes."""

    # Runtime state (mutable after creation)
    loop_device: Str64 | None = None
    """Loop device path (e.g., /dev/loop10). Set after attach_loop()."""
    host_mount_point: Str256 | None = None
    """Gateway-side mount point path. Set after mount_to_host()."""

    @property
    def disk_path(self) -> str:
        """Full path to the disk image file."""
        return sync_os.path.join(self.vdisks_base_dir, f"{self.container_name}.img")

    @property
    def mount_point_path(self) -> str:
        """Full path to the mount point directory."""
        return sync_os.path.join(self.worker_mounts_dir, self.container_name)

    async def create(self) -> None:
        """
        Create a sparse disk image file.

        Uses truncate to create a sparse file that only allocates blocks
        when written, saving disk space.
        """
        l.info(f"Creating virtual disk: {self.disk_path}")
        await run_cmd(["truncate", "-s", f"{self.size_mb}M", self.disk_path])

    async def attach_loop(self) -> str:
        """
        Attach the disk image to a loop device.

        Returns:
            The loop device path (e.g., /dev/loop10).

        Raises:
            RuntimeError: If losetup returns invalid device path.
        """
        l.info(f"Associating {self.disk_path} with a loop device...")
        stdout, _ = await run_cmd(["losetup", "--find", "--show", self.disk_path])
        self.loop_device = stdout.decode(errors='replace').strip()

        # Strict validation: must be exactly /dev/loopN format
        if not re.match(r'^/dev/loop\d+$', self.loop_device):
            raise RuntimeError(f"Invalid loop device path returned: {self.loop_device!r}")

        l.success(f"Associated disk for {self.container_name} with {self.loop_device}")
        return self.loop_device

    async def format(self) -> None:
        """
        Format the loop device with ext4 filesystem.

        Must be called after attach_loop().

        Raises:
            RuntimeError: If loop_device is not set.
        """
        if not self.loop_device:
            raise RuntimeError("Cannot format: loop device not attached")

        l.info(f"Formatting loop device {self.loop_device}...")
        await run_cmd(["mkfs.ext4", "-F", self.loop_device])

    async def mount_to_host(self) -> str:
        """
        Mount the loop device to the Gateway's filesystem.

        Creates the mount point directory, verifies it's not a symlink,
        and mounts with nosymfollow option for security.

        Returns:
            The mount point path.

        Raises:
            RuntimeError: If loop_device is not set.
            PermissionError: If mount point is a symlink (security check).
        """
        if not self.loop_device:
            raise RuntimeError("Cannot mount: loop device not attached")

        mount_point = self.mount_point_path
        await async_os.makedirs(mount_point, exist_ok=True)

        # Security: Verify mount point is not a symlink before mounting
        if await async_os.path.islink(mount_point):
            raise PermissionError(f"Mount point is a symlink: {mount_point}")

        # Mount with nosymfollow option (Linux 5.10+) to prevent symlink attacks
        await run_cmd(["mount", "-o", "nosymfollow", self.loop_device, mount_point])
        self.host_mount_point = mount_point

        l.info(f"Mounted {self.loop_device} to {mount_point} (lifecycle bound)")
        return mount_point

    async def destroy(self) -> None:
        """
        Unified cleanup (single source of truth).

        Performs cleanup in the correct order:
        1. Unmount Gateway-side mount point
        2. Detach loop device
        3. Remove disk image file

        This method is idempotent - safe to call multiple times.
        All errors are logged but do not propagate (best-effort cleanup).
        """
        l.warning(f"Destroying virtual disk for: {self.container_name}")

        # 1. Unmount Gateway-side mount point
        if self.host_mount_point:
            try:
                await run_cmd(["umount", self.host_mount_point], check=False)
                await async_os.rmdir(self.host_mount_point)
                l.info(f"Unmounted and removed {self.host_mount_point}")
            except Exception as e:
                l.warning(f"Unmount failed for {self.host_mount_point}: {e}")
            self.host_mount_point = None

        # 2. Detach loop device
        if self.loop_device and self.loop_device.strip():
            try:
                l.info(f"Detaching loop device {self.loop_device} for {self.container_name}")
                await run_cmd(["losetup", "-d", self.loop_device], check=False)
            except Exception as e:
                l.warning(f"Detach loop device failed for {self.loop_device}: {e}")
            self.loop_device = None

        # 3. Remove disk image file
        try:
            if await async_os.path.exists(self.disk_path):
                await async_os.remove(self.disk_path)
                l.info(f"Removed virtual disk file: {self.disk_path}")
        except Exception as e:
            l.warning(f"Remove disk file failed for {self.disk_path}: {e}")

    @classmethod
    async def cleanup_stale(
        cls,
        vdisks_base_dir: str,
        worker_mounts_dir: str,
    ) -> None:
        """
        Clean up stale resources from previous runs.

        This includes:
        1. Stale mount points (unmount and remove directories)
        2. Orphaned loop devices (detach devices attached to our disk files)
        3. Stale disk image files (remove .img files)

        This method fixes the resource leak issue where _cleanup_stale_workers
        was missing losetup -d for orphaned loop devices.

        Args:
            vdisks_base_dir: Base directory for virtual disk files.
            worker_mounts_dir: Directory for mount points.
        """
        l.info("Cleaning up stale virtual disk resources...")

        # 1. Clean up stale mount points
        if await async_os.path.exists(worker_mounts_dir):
            for dir_name in await async_os.listdir(worker_mounts_dir):
                dir_path = sync_os.path.join(worker_mounts_dir, dir_name)
                if await async_os.path.isdir(dir_path):
                    l.warning(f"Found stale mount point: {dir_path}. Cleaning up...")
                    try:
                        await run_cmd(["umount", dir_path], check=False)
                        l.info(f"Unmounted stale mount point: {dir_path}")
                    except Exception as e:
                        l.warning(f"Umount failed for {dir_path} (may already be unmounted): {e}")
                    try:
                        await async_os.rmdir(dir_path)
                        l.info(f"Removed stale mount point directory: {dir_path}")
                    except Exception as e:
                        l.error(f"Failed to remove stale mount point {dir_path}: {e}")

        # 2. Clean up orphaned loop devices (FIX: this was missing in original code)
        # Find all loop devices attached to our disk files
        if await async_os.path.exists(vdisks_base_dir):
            try:
                stdout, _ = await run_cmd(["losetup", "-a"], check=False)
                losetup_output = stdout.decode(errors='replace')

                # losetup -a format: /dev/loop0: [64769]:123456 (/virtual_disks/code-worker-xxx.img)
                for line in losetup_output.strip().split('\n'):
                    if not line or vdisks_base_dir not in line:
                        continue
                    # Use regex for safe parsing
                    match = re.match(r'^(/dev/loop\d+):', line)
                    if not match:
                        l.warning(f"Unexpected losetup output format: {line}")
                        continue
                    loop_device = match.group(1)
                    l.warning(f"Found orphaned loop device: {loop_device}. Detaching...")
                    try:
                        await run_cmd(["losetup", "-d", loop_device], check=False)
                        l.info(f"Detached orphaned loop device: {loop_device}")
                    except Exception as e:
                        l.error(f"Failed to detach loop device {loop_device}: {e}")
            except Exception as e:
                l.warning(f"Failed to list loop devices: {e}")

        # 3. Clean up stale virtual disk files
        if await async_os.path.exists(vdisks_base_dir):
            for filename in await async_os.listdir(vdisks_base_dir):
                if filename.endswith(".img"):
                    file_path = sync_os.path.join(vdisks_base_dir, filename)
                    l.warning(f"Found stale virtual disk file: {filename}. Removing...")
                    try:
                        await async_os.remove(file_path)
                        l.info(f"Removed stale virtual disk file: {file_path}")
                    except Exception as e:
                        l.error(f"Failed to remove stale disk file {file_path}: {e}")
