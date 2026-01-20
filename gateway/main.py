"""
Code Interpreter Gateway application entry point.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as l

from gateway import meta_config
from gateway.fastapis import router
from gateway.models.worker import Worker, WorkerPool
from gateway.utils.http_exceptions import raise_internal_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    l.info("Starting Code Interpreter Gateway")
    l.info(f"Auth token: {meta_config.AUTH_TOKEN}")

    await Worker.initialize_http_session()
    await WorkerPool.init()
    recycling_task = asyncio.create_task(WorkerPool.recycle_timed_out_workers())

    yield

    recycling_task.cancel()
    l.info("Shutting down. Cleaning up all worker containers...")
    await WorkerPool.close()
    await Worker.close_http_session()


app = FastAPI(title="Code Interpreter Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=meta_config.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def handle_unexpected_exceptions(request: Request, exc: Exception):
    l.exception(f"Unhandled exception for request: {request.method} {request.url.path}")
    raise_internal_error()


app.include_router(router)
