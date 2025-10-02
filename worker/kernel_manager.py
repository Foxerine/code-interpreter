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
        """启动并连接到一个新的 Jupyter Kernel 实例，带有重试机制以提高启动稳定性。"""
        if cls._kernel_id:
            l.warning("Kernel 已经启动。")
            return

        l.info("正在尝试启动并连接到新的 Jupyter Kernel...")
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
                    l.success(f"🚀 Jupyter Kernel 已成功创建, ID: {cls._kernel_id}")
                    await cls._establish_websocket_connection()

                    l.info("正在初始化 Kernel 环境...")
                    init_result = await cls.execute_code(cls._MATPLOTLIB_FONT_PREP_CODE, is_initialization=True)
                    if init_result.status != "ok":
                        l.error(f"🔥 Kernel 环境初始化失败: {init_result.value}")
                        await cls._shutdown_kernel()
                        raise RuntimeError("Kernel 环境初始化失败。")
                    l.success("✅ Kernel 环境初始化成功。")
                    return
            except httpx.RequestError as e:
                l.warning(f"无法连接到 Jupyter Server (尝试 {attempt + 1}/{max_retries}): {e}。将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
            except Exception:
                await cls._shutdown_kernel()
                raise

        l.error(f"🔥 启动 Jupyter Kernel 失败，已达到最大重试次数 ({max_retries})。")
        raise RuntimeError("无法连接到 Jupyter Server。请检查 Jupyter 服务的日志。")

    @classmethod
    async def _shutdown_kernel(cls):
        """关闭并清理当前的 kernel。"""
        if not cls._kernel_id:
            return
        kernel_id = cls._kernel_id
        cls._kernel_id = None
        l.warning(f"正在关闭 Kernel {kernel_id}...")
        try:
            if cls._ws_connection and cls._ws_connection.state is OPEN:
                await cls._ws_connection.close()
            cls._ws_connection = None

            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(f'{cls.JUPYTER_API_URL}/api/kernels/{kernel_id}')
            l.info(f"Kernel {kernel_id} 已成功关闭。")
        except httpx.RequestError as e:
            l.warning(f"关闭 kernel {kernel_id} 时出错: {e}")
        except Exception as e:
            l.error(f"关闭 kernel {kernel_id} 时发生意外错误: {e}")

    @classmethod
    async def _establish_websocket_connection(cls) -> None:
        """建立到 Kernel 的 WebSocket 连接"""
        if cls._ws_connection and cls._ws_connection.state is OPEN:
            await cls._ws_connection.close()
        try:
            cls._ws_connection = await connect(
                uri=f'{cls.JUPYTER_WS_URL}/api/kernels/{cls._kernel_id}/channels'
            )
            l.info("🔌 已建立到 Kernel 的 WebSocket 连接。")
        except WebSocketException as e:
            l.error(f"🔥 建立 WebSocket 连接失败: {e}")
            cls._ws_connection = None
            raise

    @classmethod
    async def is_healthy(cls) -> bool:
        """检查 WebSocket 连接是否健康"""
        if cls._ws_connection is None or cls._ws_connection.state is not OPEN:
            return False
        try:
            await asyncio.wait_for(cls._ws_connection.ping(), timeout=2.0)
            return True
        except (asyncio.TimeoutError, ConnectionClosed, WebSocketException):
            return False

    @classmethod
    async def reset_kernel(cls) -> bool:
        """通过 Supervisor 重启 Kernel 进程来重置它"""
        l.warning("🚨 正在重置 Jupyter Kernel...")
        async with cls._lock:
            process_name = 'jupyter_kernel'
            try:
                cls._supervisor.supervisor.stopProcess(process_name)
                l.info(f"🛑 {process_name} 进程已停止。")
                for _ in range(10): # 等待最多10秒
                    await asyncio.sleep(1)
                    state_info = cls._supervisor.supervisor.getProcessInfo(process_name)
                    if state_info['state'] == 20:  # RUNNING
                        l.info(f"✅ {process_name} 进程已由 Supervisor 重启。")
                        # 清理旧状态并重新初始化
                        cls._kernel_id = None
                        if cls._ws_connection:
                            await cls._ws_connection.close()
                        cls._ws_connection = None
                        await cls.start_kernel()
                        return True
                l.error(f"🔥 {process_name} 未能在时限内重启。")
                return False
            except Exception as e:
                l.error(f"🔥 Kernel 重置过程中发生错误: {e}")
                return False


    @classmethod
    async def execute_code(cls, code: str, is_initialization: bool = False) -> ExecutionResult:
        """在 Kernel 中执行代码并返回结果"""
        if not is_initialization:
            code_preview = (code[:97] + '...' if len(code) > 100 else code).replace('\n', ' ')
            l.info(f"▶️  准备执行代码: {code_preview.strip()}")
            start_time = time.monotonic()

        escaped_code = json.dumps(code)[1:-1]

        async with cls._lock:
            if not await cls.is_healthy():
                l.warning("WebSocket 连接不健康，正在尝试重连...")
                try:
                    await cls._establish_websocket_connection()
                except WebSocketException:
                    return ExecutionResult(status="error", type='connection_error', value="执行引擎连接丢失。")

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
                # [更新] 使用新的消息处理函数
                result = await asyncio.wait_for(
                    cls._process_execution_messages(msg_id),
                    timeout=cls.EXECUTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                l.warning(f"代码执行超时（超过 {cls.EXECUTION_TIMEOUT} 秒）。")
                result = ExecutionResult(
                    status="timeout", type='timeout_error',
                    value=f"代码执行超时（超过 {cls.EXECUTION_TIMEOUT} 秒）。"
                )
            except ConnectionClosed:
                l.error("连接在发送前或发送过程中被关闭。")
                result = ExecutionResult(status="error", type='connection_error', value="执行引擎连接丢失。")

            if not is_initialization:
                end_time = time.monotonic()
                duration = (end_time - start_time) * 1000
                l.info(f"⏹️  代码执行完成. 状态: {result.status.upper()}, 耗时: {duration:.2f} ms")

            return result

    @classmethod
    async def _process_execution_messages(cls, msg_id: str) -> ExecutionResult:
        """
        [重构] 处理从 Kernel 返回的所有消息，直到执行状态变为空闲。
        这个新版本会累积结果，优先返回图像。
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
                        # 优先保留图片结果
                        result_base64 = content['data']['image/png']

                elif msg_type == 'error':
                    error_output = f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                    # 出现错误，可以提前退出循环
                    break

                elif msg_type == 'status' and content.get('execution_state') == 'idle':
                    # 这是执行结束的信号，退出循环
                    break

            except (ConnectionClosed, WebSocketException) as e:
                return ExecutionResult(status="error", type='connection_error',
                                       value=f"执行引擎连接丢失: {type(e).__name__}")
            except Exception as e:
                return ExecutionResult(status="error", type='processing_error', value=f"发生意外的处理错误: {e}")

        # -- 循环结束后，根据收集到的结果决定最终返回值 --
        if error_output:
            return ExecutionResult(status="error", type='execution_error', value=error_output)

        if result_base64:
            return ExecutionResult(status="ok", type='image_png_base64', value=result_base64)

        final_text = "".join(result_text_parts)
        return ExecutionResult(status="ok", type='text', value=final_text)
