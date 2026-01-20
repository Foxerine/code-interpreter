"""
/api/v1 routes aggregation with global authentication.
"""
from fastapi import Depends

from gateway.fastapis.deps import verify_token
from gateway.fastapis.tagged_api_router import TaggedAPIRouter

from .execute import router as execute_router
from .release import router as release_router
from .files import router as files_router
from .status import router as status_router

router = TaggedAPIRouter(prefix="/v1", dependencies=[Depends(verify_token)])
router.include_router(execute_router)
router.include_router(release_router)
router.include_router(files_router)
router.include_router(status_router)
