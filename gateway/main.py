import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as l
from starlette.status import HTTP_204_NO_CONTENT

import config
from dto import (
    ExecuteRequest,
    ExecuteResponse,
    ReleaseRequest,
)
from utils import raise_internal_error
from worker_manager import WorkerManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    l.info(f"token: {config.AUTH_TOKEN}")

    # [更新] 传递所有可配置的参数
    await WorkerManager.init(
        worker_image_name=config.WORKER_IMAGE_NAME,
        internal_network_name=config.INTERNAL_NETWORK_NAME,
        min_idle_workers=config.MIN_IDLE_WORKERS,
        max_total_workers=config.MAX_TOTAL_WORKERS,
        worker_idle_timeout=config.WORKER_IDLE_TIMEOUT,
        recycling_interval=config.RECYCLING_INTERVAL,
        gateway_internal_ip=config.GATEWAY_INTERNAL_IP,
        worker_max_disk_size_mb=config.WORKER_MAX_DISK_SIZE_MB,
        worker_cpu=config.WORKER_CPU,
        worker_ram_mb=config.WORKER_RAM_MB,
    )

    recycling_task = asyncio.create_task(WorkerManager.recycle_timed_out_workers())
    yield
    recycling_task.cancel()
    l.info("Shutting down. Cleaning up all worker containers...")
    await WorkerManager.close()


app = FastAPI(title="Code Interpreter Gateway", lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],  # 允许所有请求头 (包括 X-Auth-Token)
)

@app.exception_handler(Exception)
async def handle_unexpected_exceptions(request: Request, exc: Exception):
    """
    捕获所有未经处理的异常，防止敏感信息泄露。
    """
    # 1. 为开发人员记录详细的、包含完整堆栈跟踪的错误日志
    l.exception(
        f"An unhandled exception occurred for request: {request.method} {request.url.path}"
    )

    raise_internal_error()

# --- Security ---
async def verify_token(x_auth_token: str = Header()):
    if x_auth_token != config.AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")

# --- API Endpoints ---
@app.post(
    "/execute",
    dependencies=[Depends(verify_token)],
)
async def execute(request: ExecuteRequest) -> ExecuteResponse:
    worker = await WorkerManager.get_worker_for_user(request.user_uuid)
    if not worker:
        raise HTTPException(status_code=503, detail="No available workers at the moment, please try again later.")

    # Proxy the request to the assigned worker
    try:
        async with httpx.AsyncClient() as client:
            worker_request_body = {"code": request.code}
            response = await client.post(
                f"{worker.internal_url}/execute",
                json=worker_request_body,
                timeout=config.MAX_EXECUTION_TIMEOUT # A reasonable timeout for the whole operation
            )
            # Forward the worker's response (both success and error)
            if response.status_code == 503:
                await WorkerManager.release_worker_by_user(request.user_uuid)
                raise HTTPException(
                    status_code=response.status_code,
                    detail="The code resulted in an execution timeout or a crashed environment or resource exhaustion. "
                           "The environment has been reset, "
                           "please try again."
                )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Worker returned an unknown error.")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            return ExecuteResponse(**response.json())
    except httpx.RequestError as e:
        l.error(f"Failed to proxy request to worker {worker.container_name}: {e}")
        await WorkerManager.release_worker_by_user(request.user_uuid)
        raise HTTPException(status_code=504, detail="Gateway Timeout: Could not connect to the execution worker. The environment has been reset, please try again.")
    except HTTPException as he:
        raise
    except Exception as e:
        l.exception(e)
        await WorkerManager.release_worker_by_user(request.user_uuid)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/release", status_code=HTTP_204_NO_CONTENT, dependencies=[Depends(verify_token)])
async def release(request: ReleaseRequest):
    await WorkerManager.release_worker_by_user(request.user_uuid)

@app.get(
    "/status",
    dependencies=[Depends(verify_token)],
)
async def get_status():
    return {
        "total_workers": len(WorkerManager.workers),
        "busy_workers": len(WorkerManager.user_to_worker_map),
        "is_initializing": WorkerManager._is_initializing,
    }
