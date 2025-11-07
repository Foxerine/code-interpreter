# worker/kernel_manager.py

"""
Manages the lifecycle and interaction with a stateful Jupyter Kernel.
This module is fully compliant with the websockets library's best practices.
"""
import asyncio
import json
import time
from uuid import uuid4
from xmlrpc.client import ServerProxy

import httpx
from loguru import logger as l
from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import OPEN

from dto import ExecutionResult


class KernelDeadError(Exception):
    pass


class JupyterKernelManager:
    """A static manager for a persistent Jupyter Kernel."""
    # --- Constants ---
    JUPYTER_HOST: str = "127.0.0.1:8888"
    JUPYTER_API_URL: str = f"http://{JUPYTER_HOST}"
    JUPYTER_WS_URL: str = f"ws://{JUPYTER_HOST}"
    EXECUTION_TIMEOUT: float = 10.0

    _MATPLOTLIB_FONT_PREP_CODE: str = (
        "import matplotlib\n"
        "matplotlib.rcParams['font.family'] = ['SimHei']\n"
        "matplotlib.rcParams['axes.unicode_minus'] = False\n"
    )

    # --- State ---
    _kernel_id: str | None = None
    _ws_connection: ClientConnection | None = None
    _lock = asyncio.Lock()
    _supervisor = ServerProxy('http://127.0.0.1:9001/RPC2')

    @classmethod
    async def start_kernel(cls) -> None:
        """Starts and connects to a new Jupyter Kernel instance with retry mechanism for improved startup stability."""
        if cls._kernel_id:
            l.warning("Kernel is already running.")
            return

        l.info("Attempting to start and connect to a new Jupyter Kernel...")
        max_retries = 10
        retry_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        url=f'{cls.JUPYTER_API_URL}/api/kernels',
                        json={'name': "python"},
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    kernel_data = response.json()
                    cls._kernel_id = kernel_data['id']
                    l.success(f"Jupyter Kernel created successfully, ID: {cls._kernel_id}")
                    await cls._establish_websocket_connection()

                    l.info("Initializing Kernel environment...")
                    init_result = await cls.execute_code(cls._MATPLOTLIB_FONT_PREP_CODE, is_initialization=True)
                    if init_result.status != "ok":
                        l.error(f"Kernel environment initialization failed: {init_result.value}")
                        await cls._shutdown_kernel()
                        raise RuntimeError("Kernel environment initialization failed.")
                    l.success("Kernel environment initialized successfully.")
                    return
            except httpx.RequestError as e:
                l.warning(f"Unable to connect to Jupyter Server (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            except Exception:
                await cls._shutdown_kernel()
                raise

        l.error(f"Failed to start Jupyter Kernel after maximum retries ({max_retries}).")
        raise RuntimeError("Unable to connect to Jupyter Server. Please check the Jupyter service logs.")

    @classmethod
    async def _shutdown_kernel(cls):
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

            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(f'{cls.JUPYTER_API_URL}/api/kernels/{kernel_id}')
            l.info(f"Kernel {kernel_id} shut down successfully.")
        except httpx.RequestError as e:
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
    async def reset_kernel(cls) -> bool:
        """Resets the Kernel by restarting the Kernel process via Supervisor."""
        l.warning("Resetting Jupyter Kernel...")
        async with cls._lock:
            process_name = 'jupyter_kernel'
            try:
                cls._supervisor.supervisor.stopProcess(process_name)
                l.info(f"{process_name} process stopped.")
                for _ in range(10):  # Wait up to 10 seconds
                    await asyncio.sleep(1)
                    state_info = cls._supervisor.supervisor.getProcessInfo(process_name)
                    if state_info['state'] == 20:  # RUNNING
                        l.info(f"{process_name} process restarted by Supervisor.")
                        # Clean up old state and reinitialize
                        cls._kernel_id = None
                        if cls._ws_connection:
                            await cls._ws_connection.close()
                        cls._ws_connection = None
                        await cls.start_kernel()
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

        async with cls._lock:
            if not await cls.is_healthy():
                l.warning("WebSocket connection unhealthy, attempting to reconnect...")
                try:
                    await cls._establish_websocket_connection()
                except WebSocketException:
                    return ExecutionResult(status="error", type='connection_error', value="Execution engine connection lost.")

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
                # Use the new message processing function
                result = await asyncio.wait_for(
                    cls._process_execution_messages(msg_id),
                    timeout=cls.EXECUTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                l.warning(f"Code execution timed out (exceeded {cls.EXECUTION_TIMEOUT} seconds).")
                result = ExecutionResult(
                    status="timeout", type='timeout_error',
                    value=f"Code execution timed out (exceeded {cls.EXECUTION_TIMEOUT} seconds)."
                )
            except ConnectionClosed:
                l.error("Connection closed before or during send.")
                result = ExecutionResult(status="error", type='connection_error', value="Execution engine connection lost.")

            if not is_initialization:
                end_time = time.monotonic()
                duration = (end_time - start_time) * 1000
                l.info(f"Code execution completed. Status: {result.status.upper()}, Duration: {duration:.2f} ms")

            return result

    @classmethod
    async def _process_execution_messages(cls, msg_id: str) -> ExecutionResult:
        """
        Processes all messages returned from the Kernel until execution state becomes idle.
        This version accumulates results and prioritizes returning images.
        """
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
                    return ExecutionResult(status='kernel_error', type='processing_error', value='kernel dead')

                if msg_type == 'stream':
                    result_text_parts.append(content.get('text', ''))

                elif msg_type == 'execute_result':
                    result_text_parts.append(content.get('data', {}).get('text/plain', ''))

                elif msg_type == 'display_data':
                    if 'image/png' in content.get('data', {}):
                        # Prioritize image results
                        result_base64 = content['data']['image/png']

                elif msg_type == 'error':
                    error_output = f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                    # Exit loop early on error
                    break

                elif msg_type == 'status' and content.get('execution_state') == 'idle':
                    # This signals the end of execution, exit loop
                    break

            except (ConnectionClosed, WebSocketException) as e:
                return ExecutionResult(status="error", type='connection_error',
                                       value=f"Execution engine connection lost: {type(e).__name__}")
            except Exception as e:
                return ExecutionResult(status="error", type='processing_error', value=f"Unexpected processing error: {e}")

        # After loop ends, decide final return value based on collected results
        if error_output:
            return ExecutionResult(status="error", type='execution_error', value=error_output)

        if result_base64:
            return ExecutionResult(status="ok", type='image_png_base64', value=result_base64)

        final_text = "".join(result_text_parts)
        return ExecutionResult(status="ok", type='text', value=final_text)
