"""
/kernel routes aggregation.
"""
from worker.fastapis.tagged_api_router import TaggedAPIRouter

from .execute import router as execute_router
from .health import router as health_router
from .reset import router as reset_router

router = TaggedAPIRouter(prefix="/kernel", tag="Kernel")
router.include_router(health_router)
router.include_router(reset_router)
router.include_router(execute_router)
