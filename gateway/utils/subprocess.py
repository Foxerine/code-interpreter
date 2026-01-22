"""
Async subprocess utilities.
"""
import asyncio


async def run_cmd(cmd: list[str], check: bool = True) -> tuple[bytes, bytes]:
    """
    Execute a shell command asynchronously.

    Args:
        cmd: Command and arguments to execute.
        check: If True, raises RuntimeError on non-zero exit code.

    Returns:
        Tuple of (stdout, stderr) bytes.

    Raises:
        RuntimeError: If check=True and command exits with non-zero code.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if check and process.returncode != 0:
        try:
            stderr_str = stderr.decode()
        except UnicodeDecodeError:
            stderr_str = stderr.decode(errors='replace')
        raise RuntimeError(
            f"Command failed with exit code {process.returncode}: {' '.join(cmd)}\n"
            f"stderr: {stderr_str}"
        )
    return stdout, stderr
