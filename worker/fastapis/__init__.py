"""
Worker FastAPI routes aggregation.
"""
from .tagged_api_router import TaggedAPIRouter
from .api import router as api_router

router = TaggedAPIRouter()
router.include_router(api_router)
