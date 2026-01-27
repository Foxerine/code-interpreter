"""
JupyterKernel rich domain model.
"""
import asyncio
import json
import time
from enum import StrEnum
from typing import ClassVar
from uuid import uuid4
from xmlrpc.client import ServerProxy

import aiohttp
from loguru import logger as l
from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import OPEN

from worker.utils.aiohttp_client_session_mixin import AioHttpClientSessionClassVarMixin
from worker import meta_config
from .base import ModelBase


class ExecutionStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    KERNEL_ERROR = "kernel_error"


class ExecutionResultType(StrEnum):
    TEXT = "text"
    IMAGE_PNG_BASE64 = "image_png_base64"
    CONNECTION_ERROR = "connection_error"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT_ERROR = "timeout_error"
    PROCESSING_ERROR = "processing_error"


class ExecutionResult(ModelBase):
    """Result from code execution."""
    status: ExecutionStatus
    type: ExecutionResultType
    value: str | None = None


class JupyterKernel(AioHttpClientSessionClassVarMixin):
    """
    Rich domain model for Jupyter Kernel management.

    This class uses classmethod pattern for singleton-like behavior.
    Inherits AioHttpClientSessionClassVarMixin for shared HTTP session.
    """
    JUPYTER_HOST: ClassVar[str] = "127.0.0.1:8888"
    JUPYTER_API_URL: ClassVar[str] = f"http://{JUPYTER_HOST}"
    JUPYTER_WS_URL: ClassVar[str] = f"ws://{JUPYTER_HOST}"
    EXECUTION_TIMEOUT: ClassVar[float] = meta_config.EXECUTION_TIMEOUT

    # Reusable timeout for kernel API calls
    _API_TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(total=5.0)

    _MATPLOTLIB_FONT_PREP_CODE: ClassVar[str] = (
        "import matplotlib\n"
        "matplotlib.rcParams['font.family'] = ['SimHei']\n"
        "matplotlib.rcParams['axes.unicode_minus'] = False\n"
    )

    _kernel_id: ClassVar[str | None] = None
    _ws_connection: ClassVar[ClientConnection | None] = None
    _lock: ClassVar[asyncio.Lock | None] = None
    """Initialized at runtime in start() to avoid event loop issues"""
    _supervisor: ClassVar[ServerProxy] = ServerProxy('http://127.0.0.1:9001/RPC2')

    def __new__(cls, *args, **kwargs):
        raise RuntimeError(f"{cls.__name__} is a pure classmethod singleton, cannot be instantiated")

    @classmethod
    async def start(cls) -> None:
        """Starts and connects to a new Jupyter Kernel instance."""
        if cls._kernel_id:
            l.warning("Kernel is already running.")
            return

        # Initialize lock at runtime to ensure it's bound to the current event loop
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        l.info("Attempting to start and connect to a new Jupyter Kernel...")
        # TODO: Move max_retries (10), retry_delay (1.0), and timeout (5.0) to meta_config
        max_retries = 10
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with cls.get_http_session().post(
                    url=f'{cls.JUPYTER_API_URL}/api/kernels',
                    json={'name': "python"},
                    headers={'Content-Type': 'application/json'},
                    timeout=cls._API_TIMEOUT,
                ) as response:
                    response.raise_for_status()
                    kernel_data = await response.json()
                    cls._kernel_id = kernel_data['id']
                    l.success(f"Jupyter Kernel created successfully, ID: {cls._kernel_id}")
                    await cls._establish_websocket_connection()

                    l.info("Initializing Kernel environment...")
                    init_result = await cls.execute_code(cls._MATPLOTLIB_FONT_PREP_CODE, is_initialization=True)
                    if init_result.status != ExecutionStatus.OK:
                        l.error(f"Kernel environment initialization failed: {init_result.value}")
                        await cls._shutdown()
                        raise RuntimeError("Kernel environment initialization failed.")
                    l.success("Kernel environment initialized successfully.")
                    return
            except aiohttp.ClientError as e:
                l.warning(f"Unable to connect to Jupyter Server (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            except Exception:
                await cls._shutdown()
                raise

        l.error(f"Failed to start Jupyter Kernel after maximum retries ({max_retries}).")
        raise RuntimeError("Unable to connect to Jupyter Server. Please check the Jupyter service logs.")

    @classmethod
    async def _shutdown(cls) -> None:
        """Shuts down and cleans up the current kernel."""
        if not cls._kernel_id:
            return
        kernel_id = cls._kernel_id
        cls._kernel_id = None
        l.warning(f"Shutting down Kernel {kernel_id}...")
        try:
            if cls._ws_connection and cls._ws_connection.state is OPEN:
                await cls._ws_connection.close()
            cls._ws_connection = None

            # TODO: Move timeout to meta_config
            async with cls.get_http_session().delete(
                f'{cls.JUPYTER_API_URL}/api/kernels/{kernel_id}',
                timeout=cls._API_TIMEOUT,
            ) as response:
                pass  # We don't need to check response for delete
            l.info(f"Kernel {kernel_id} shut down successfully.")
        except aiohttp.ClientError as e:
            l.warning(f"Error shutting down kernel {kernel_id}: {e}")
        except Exception as e:
            l.error(f"Unexpected error shutting down kernel {kernel_id}: {e}")

    @classmethod
    async def _establish_websocket_connection(cls) -> None:
        """Establishes WebSocket connection to the Kernel."""
        if cls._ws_connection and cls._ws_connection.state is OPEN:
            await cls._ws_connection.close()
        try:
            cls._ws_connection = await connect(
                uri=f'{cls.JUPYTER_WS_URL}/api/kernels/{cls._kernel_id}/channels'
            )
            l.info("WebSocket connection to Kernel established.")
        except WebSocketException as e:
            l.error(f"Failed to establish WebSocket connection: {e}")
            cls._ws_connection = None
            raise

    @classmethod
    async def is_healthy(cls) -> bool:
        """Checks if the WebSocket connection is healthy."""
        if cls._ws_connection is None or cls._ws_connection.state is not OPEN:
            return False
        try:
            await asyncio.wait_for(cls._ws_connection.ping(), timeout=2.0)
            return True
        except (asyncio.TimeoutError, ConnectionClosed, WebSocketException):
            return False

    @classmethod
    async def reset(cls) -> bool:
        """Resets the Kernel by restarting the Kernel process via Supervisor."""
        l.warning("Resetting Jupyter Kernel...")
        assert cls._lock is not None, "Kernel.start() must be called before reset()"
        async with cls._lock:
            process_name = 'jupyter_kernel'
            try:
                cls._supervisor.supervisor.stopProcess(process_name)
                l.info(f"{process_name} process stopped.")
                for _ in range(10):
                    await asyncio.sleep(1)
                    state_info = cls._supervisor.supervisor.getProcessInfo(process_name)
                    if state_info['state'] == 20:  # RUNNING
                        l.info(f"{process_name} process restarted by Supervisor.")
                        cls._kernel_id = None
                        if cls._ws_connection:
                            await cls._ws_connection.close()
                        cls._ws_connection = None
                        await cls.start()
                        return True
                l.error(f"{process_name} failed to restart within timeout.")
                return False
            except Exception as e:
                l.error(f"Error during Kernel reset: {e}")
                return False

    @classmethod
    async def execute_code(cls, code: str, is_initialization: bool = False) -> ExecutionResult:
        """Executes code in the Kernel and returns the result."""
        if not is_initialization:
            code_preview = (code[:97] + '...' if len(code) > 100 else code).replace('\n', ' ')
            l.info(f"Preparing to execute code: {code_preview.strip()}")
            start_time = time.monotonic()

        escaped_code = json.dumps(code)[1:-1]

        assert cls._lock is not None, "Kernel.start() must be called before execute_code()"
        async with cls._lock:
            if not await cls.is_healthy():
                l.warning("WebSocket connection unhealthy, attempting to reconnect...")
                try:
                    await cls._establish_websocket_connection()
                except WebSocketException:
                    return ExecutionResult(status=ExecutionStatus.ERROR, type=ExecutionResultType.CONNECTION_ERROR, value="Execution engine connection lost.")

            assert cls._ws_connection is not None
            msg_id = uuid4().hex
            execute_request = f'''
            {{
                "header": {{
                    "msg_id": "{msg_id}", "username": "api", "session": "{uuid4().hex}",
                    "msg_type": "execute_request", "version": "5.3"
                }},
                "parent_header": {{}}, "metadata": {{}},
                "content": {{
                    "code": "{escaped_code}", "silent": false, "store_history": false,
                    "user_expressions": {{}}, "allow_stdin": false
                }}, "buffers": [], "channel": "shell"
            }}
            '''
            try:
                await cls._ws_connection.send(execute_request)
                result = await asyncio.wait_for(
                    cls._process_execution_messages(msg_id),
                    timeout=cls.EXECUTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                l.warning(f"Code execution timed out (exceeded {cls.EXECUTION_TIMEOUT} seconds).")
                result = ExecutionResult(
                    status=ExecutionStatus.TIMEOUT, type=ExecutionResultType.TIMEOUT_ERROR,
                    value=f"Code execution timed out (exceeded {cls.EXECUTION_TIMEOUT} seconds)."
                )
            except (ConnectionClosed, WebSocketException) as e:
                l.error(f"WebSocket error during execution: {type(e).__name__}")
                result = ExecutionResult(status=ExecutionStatus.ERROR, type=ExecutionResultType.CONNECTION_ERROR, value="Execution engine connection lost.")

            if not is_initialization:
                end_time = time.monotonic()
                duration_secs = end_time - start_time
                l.info(f"Code execution completed. Status: {result.status.upper()}, Duration: {duration_secs:.2f}s")

            return result

    @classmethod
    async def _process_execution_messages(cls, msg_id: str) -> ExecutionResult:
        """Processes all messages returned from the Kernel until execution state becomes idle."""
        assert cls._ws_connection is not None

        result_text_parts = []
        result_base64 = None
        error_output = None

        while True:
            try:
                message_raw = await cls._ws_connection.recv()
                msg = json.loads(message_raw)
                l.debug(msg)

                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue

                msg_type = msg["msg_type"]
                content = msg.get("content", {})

                if content.get('execution_state') == 'dead':
                    return ExecutionResult(status=ExecutionStatus.KERNEL_ERROR, type=ExecutionResultType.PROCESSING_ERROR, value='kernel dead')

                if msg_type == 'stream':
                    result_text_parts.append(content.get('text', ''))

                elif msg_type == 'execute_result':
                    result_text_parts.append(content.get('data', {}).get('text/plain', ''))

                elif msg_type == 'display_data':
                    if 'image/png' in content.get('data', {}):
                        result_base64 = content['data']['image/png']

                elif msg_type == 'error':
                    error_output = f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                    break

                elif msg_type == 'status' and content.get('execution_state') == 'idle':
                    break

            except (ConnectionClosed, WebSocketException) as e:
                return ExecutionResult(status=ExecutionStatus.ERROR, type=ExecutionResultType.CONNECTION_ERROR,
                                       value=f"Execution engine connection lost: {type(e).__name__}")
            except Exception as e:
                return ExecutionResult(status=ExecutionStatus.ERROR, type=ExecutionResultType.PROCESSING_ERROR, value=f"Unexpected processing error: {e}")

        if error_output:
            return ExecutionResult(status=ExecutionStatus.ERROR, type=ExecutionResultType.EXECUTION_ERROR, value=error_output)

        if result_base64:
            return ExecutionResult(status=ExecutionStatus.OK, type=ExecutionResultType.IMAGE_PNG_BASE64, value=result_base64)

        final_text = "".join(result_text_parts)
        return ExecutionResult(status=ExecutionStatus.OK, type=ExecutionResultType.TEXT, value=final_text)
