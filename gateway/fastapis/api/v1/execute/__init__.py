"""
/execute endpoint.
"""
import aiohttp
import orjson
from loguru import logger as l

from gateway import meta_config
from gateway.fastapis.deps import WorkerDep
from gateway.fastapis.tagged_api_router import TaggedAPIRouter
from gateway.models.execute import ExecuteRequest, ExecuteResponse
from gateway.utils.http_exceptions import raise_gateway_timeout, raise_internal_error, raise_service_unavailable

router = TaggedAPIRouter(prefix="/execute", tag="Execute code")


@router.post("", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest, worker: WorkerDep) -> ExecuteResponse:
    l.debug(f"Execute request: {request}")
    try:
        result = await worker.execute(request.code, meta_config.MAX_EXECUTION_TIMEOUT)

        match result.status_code:
            case 200:
                return ExecuteResponse(
                    result_text=result.data.result_text,
                    result_base64=result.data.result_base64,
                )
            case 400:
                # Python execution error - return the error message as result_text
                # Worker is still healthy, no need to release
                l.debug(f"Worker {worker.container_name} returned Python error: {result.text}")
                try:
                    error_data = orjson.loads(result.text)
                    error_message = error_data.get("detail", result.text)
                except orjson.JSONDecodeError:
                    error_message = result.text
                return ExecuteResponse(result_text=error_message)
            case 503:
                l.warning(f"Worker {worker.container_name} returned 503, releasing worker")
                await worker.release()
                raise_service_unavailable(
                    "The code resulted in an execution timeout or crashed environment. "
                    "The environment has been reset, please try again."
                )
            case _:
                l.error(f"Worker {worker.container_name} returned unexpected status {result.status_code}")
                await worker.release()
                raise_internal_error()
    except aiohttp.ClientError as e:
        l.error(f"Failed to proxy request to worker {worker.container_name}: {e}")
        await worker.release()
        raise_gateway_timeout(
            "Gateway Timeout: Could not connect to the execution worker. "
            "The environment has been reset, please try again."
        )
