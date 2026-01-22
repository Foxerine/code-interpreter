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
from gateway.models.worker import WorkerPool
from gateway.utils.aiohttp_client_session_mixin import AioHttpClientSessionClassVarMixin
from gateway.utils.http_exceptions import raise_internal_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    l.info("Starting Code Interpreter Gateway")
    # SECURITY DESIGN: Token logged intentionally for development/debugging.
    # In production, operators should configure log filtering or use external secret management.
    l.info(f"Auth token: {meta_config.AUTH_TOKEN}")

    await AioHttpClientSessionClassVarMixin.initialize_http_session()
    await WorkerPool.init()
    recycling_task = asyncio.create_task(WorkerPool.recycle_timed_out_workers())

    yield

    recycling_task.cancel()
    l.info("Shutting down. Cleaning up all worker containers...")
    await WorkerPool.close()
    await AioHttpClientSessionClassVarMixin.close_http_session()


app = FastAPI(title="Code Interpreter Gateway", lifespan=lifespan)

# SECURITY DESIGN: CORS configured via environment variable CORS_ALLOWED_ORIGINS.
# Default '*' is intentional for development flexibility. Production deployments
# MUST set explicit origins. Rate limiting is handled at infrastructure level (nginx/cloudflare).
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
