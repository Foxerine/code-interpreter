"""
/api routes aggregation for Worker service.
"""
from worker.fastapis.tagged_api_router import TaggedAPIRouter

from .v1 import router as v1_router

router = TaggedAPIRouter(prefix="/api")
router.include_router(v1_router)
