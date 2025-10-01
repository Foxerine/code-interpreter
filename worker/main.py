"""
Main FastAPI application for the Python Code Interpreter WORKER service.
Authentication is handled by the Gateway. This service is not exposed publicly.
"""
import asyncio
from fastapi import FastAPI, HTTPException, status
from loguru import logger as l

from dto import ExecuteRequest, ExecuteResponse
from kernel_manager import JupyterKernelManager

# --- Application Lifecycle ---
async def _lifespan(app: FastAPI):
    l.info("Worker is starting up...")
    await JupyterKernelManager.start_kernel()
    yield
    l.info("Worker is shutting down...")

# --- FastAPI Application Instance ---
app = FastAPI(
    title="Python Code Interpreter Worker",
    lifespan=_lifespan,
)

# --- API Endpoints ---
@app.get("/health")
async def get_health_status():
    if await JupyterKernelManager.is_healthy():
        return {"status": "ok"}
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kernel is not healthy")

@app.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_python_kernel():
    if not await JupyterKernelManager.reset_kernel():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset Python kernel.",
        )

@app.post("/execute", response_model=ExecuteResponse)
async def execute_python_code(request: ExecuteRequest) -> ExecuteResponse:
    result = await JupyterKernelManager.execute_code(request.code)

    if result.status == "ok":
        return ExecuteResponse(
            result_base64=result.value if result.type == 'image_png_base64' else None,
            result_text=result.value if result.type != 'image_png_base64' else None,
        )
    elif result.status == "timeout":
        # todo 引入更完善的自愈机制，现在的机制感觉有点惩罚用户，因为会失去所有的状态

        # l.warning("Code execution timed out. Triggering kernel auto-reset.")
        # asyncio.create_task(JupyterKernelManager.reset_kernel())
        # raise HTTPException(
        #     status_code=status.HTTP_400_BAD_REQUEST,
        #     detail=f"Code execution timed out after {JupyterKernelManager.EXECUTION_TIMEOUT} seconds. Environment has been reset.",
        # )

        l.error("FATAL: Code execution timed out. This worker instance is now considered unhealthy.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Code execution timed out. This worker instance is now considered unhealthy and should be killed. ",
        )

    else:  # status == "error"
        l.warning(f"Python execution failed. Type: {result.type}, Message: {result.value}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Python Execution Error: {result.value}",
        )
